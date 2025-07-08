import os
import subprocess
import time
import asyncio # Required for FastAPI's async nature with subprocess
import logging

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Configuration
# For Render, use relative paths. The HOST_LOG_DIR will be created in the container.
# The VMX_PATH and other vmrun specific paths in `automate_sysmon_export_and_convert.py`
# will NOT work on Render as-is, as Render cannot run VMware VMs.
# This script is being adapted for Render deployment structure, but the VM operations themselves
# are environment-dependent and won't function on Render's standard service instances.
HOST_LOG_DIR = "host_log_output"  # Relative path for Render
AUTOMATION_SCRIPT_PATH = "automate_sysmon_export_and_convert.py" # Assumed to be in the same dir

# Ensure HOST_LOG_DIR exists
if not os.path.isdir(HOST_LOG_DIR):
    os.makedirs(HOST_LOG_DIR, exist_ok=True)
    logger.info(f"Created HOST_LOG_DIR at {os.path.abspath(HOST_LOG_DIR)}")

# Mount static files (if any separate CSS/JS files are used later)
# app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serves the main HTML page."""
    return templates.TemplateResponse("index.html", {"request": request})

async def run_script_and_stream_logs():
    """
    Runs the automation script and streams its output for Server-Sent Events.
    """
    process = None
    try:
        # For Render, explicitly use the Python interpreter available in the environment
        # Ensure the script has execute permissions if needed, though `python script.py` handles it.
        command = ["python", AUTOMATION_SCRIPT_PATH]

        logger.info(f"Starting automation script: {' '.join(command)}")
        yield "data: Automation process starting...\n\n"

        # asyncio.create_subprocess_exec is preferred for FastAPI
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT  # Redirect stderr to stdout
        )

        # Stream output
        while True:
            if process.stdout is None:
                break
            line_bytes = await process.stdout.readline()
            if not line_bytes: # EOF
                break
            line = line_bytes.decode('utf-8', errors='replace').strip()
            yield f"data: {line}\n\n"
            await asyncio.sleep(0.05) # Small delay to allow client to update, and prevent tight loop

        await process.wait() # Wait for the subprocess to exit
        return_code = process.returncode

        logger.info(f"Automation script finished with exit code {return_code}")

        if return_code == 0:
            yield "data: Automation completed successfully.\n\n"
            yield "data: SCRIPT_DONE\n\n"
        else:
            yield f"data: Automation failed with error code {return_code}.\n\n"
            yield f"data: SCRIPT_ERROR\n\n"

    except FileNotFoundError:
        logger.error(f"ERROR: Automation script '{AUTOMATION_SCRIPT_PATH}' not found.")
        yield f"data: ERROR: Automation script '{AUTOMATION_SCRIPT_PATH}' not found. Please check the path.\n\n"
        yield "data: SCRIPT_ERROR\n\n"
    except Exception as e:
        logger.error(f"An error occurred during automation: {str(e)}", exc_info=True)
        yield f"data: An server-side error occurred: {str(e)}\n\n"
        yield "data: SCRIPT_ERROR\n\n"
    finally:
        if process and process.returncode is None: # Check if process is still running
            logger.warning("Process was still running, attempting to terminate.")
            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=5.0) # Wait for termination
                logger.info("Process terminated.")
                yield "data: Process was terminated.\n\n"
            except asyncio.TimeoutError:
                logger.error("Failed to terminate process in time, attempting kill.")
                process.kill()
                await process.wait()
                logger.info("Process killed.")
                yield "data: Process was killed due to timeout on termination.\n\n"
            except Exception as e_term:
                logger.error(f"Error during process termination: {e_term}")
                yield f"data: Error during process termination: {e_term}\n\n"


@app.get("/run-automation")
async def run_automation_stream():
    """
    Endpoint to trigger the automation script and stream logs via SSE.
    """
    return StreamingResponse(run_script_and_stream_logs(), media_type="text/event-stream")

@app.get("/download/{filename:path}")
async def download_file(filename: str):
    """
    Serves files from the HOST_LOG_DIR.
    The ':path' converter allows filenames to include subdirectories if any were created.
    """
    logger.info(f"Download request for file: {filename} from directory: {HOST_LOG_DIR}")

    # Security: Prevent directory traversal.
    # os.path.abspath resolves '..' and symbolic links.
    # Ensure the resulting path is still within HOST_LOG_DIR.
    host_log_dir_abs = os.path.abspath(HOST_LOG_DIR)
    requested_file_path_abs = os.path.abspath(os.path.join(host_log_dir_abs, filename))

    if not requested_file_path_abs.startswith(host_log_dir_abs):
        logger.warning(f"Directory traversal attempt blocked for: {filename}. Resolved path: {requested_file_path_abs}")
        raise HTTPException(status_code=403, detail="Access denied: Invalid file path.")

    if not os.path.exists(requested_file_path_abs) or not os.path.isfile(requested_file_path_abs):
        logger.error(f"File not found: {requested_file_path_abs}")
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")

    # Use FileResponse for efficient file serving
    # The filename for attachment can be derived or set explicitly.
    # Deriving from the input 'filename' is usually fine here.
    attachment_filename = os.path.basename(filename)
    return FileResponse(requested_file_path_abs, media_type='application/octet-stream', filename=attachment_filename)

if __name__ == "__main__":
    import uvicorn
    # This is for local development. Render will use the start command in render.yaml.
    # The HOST_LOG_DIR needs to be accessible. For local dev, it's relative to where main.py is.
    # When deploying to Render, this path will be relative to the project root in the container.
    logger.info(f"Starting Uvicorn server locally. HOST_LOG_DIR is {os.path.abspath(HOST_LOG_DIR)}")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
