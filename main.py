import os
import subprocess
import time
import asyncio # Required for FastAPI's async nature with subprocess
import logging
import shutil # For saving uploaded files
from pathlib import Path # For path manipulation

from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse, JSONResponse
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
BASE_DIR = Path(__file__).resolve().parent
HOST_LOG_DIR = BASE_DIR / "host_log_output"  # Main directory for script outputs and uploads
UPLOADS_DIR = HOST_LOG_DIR / "uploads"       # Subdirectory for uploads
AUTOMATION_SCRIPT_PATH = BASE_DIR / "automate_sysmon_export_and_convert.py"

# Ensure directories exist
HOST_LOG_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
logger.info(f"Host log directory: {HOST_LOG_DIR.resolve()}")
logger.info(f"Uploads directory: {UPLOADS_DIR.resolve()}")


# Mount static files (if any separate CSS/JS files are used later)
# app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serves the main HTML page."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload")
async def upload_file_for_scan(file: UploadFile = File(...)):
    """
    Handles file uploads, saves the file temporarily, and returns its path.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided or filename is empty.")

    # Sanitize filename (basic) - more robust sanitization might be needed
    safe_filename = Path(file.filename).name
    if not safe_filename: # Handles cases like ".." or "." as filename
        raise HTTPException(status_code=400, detail="Invalid filename.")

    temp_file_path = UPLOADS_DIR / safe_filename

    try:
        with temp_file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info(f"File '{safe_filename}' uploaded successfully to '{temp_file_path}'.")
        # Return the path relative to the project base, or a unique identifier
        # For simplicity, returning path relative to HOST_LOG_DIR as the script might need that context
        return JSONResponse(content={"message": "File uploaded successfully", "filePath": str(temp_file_path.resolve())})
    except Exception as e:
        logger.error(f"Error saving uploaded file '{safe_filename}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Could not save file: {str(e)}")
    finally:
        await file.close()


async def run_scan_script_and_stream_logs(file_path_to_scan: str):
    """
    Runs the automation/scan script with the given file path and streams its output.
    """
    process = None
    # Validate file_path_to_scan - ensure it's within UPLOADS_DIR for security
    try:
        resolved_scan_path = Path(file_path_to_scan).resolve()
        if not resolved_scan_path.is_file():
            logger.error(f"Scan target file not found: {resolved_scan_path}")
            yield f"data: ERROR: Scan target file not found: {file_path_to_scan}\n\n"
            yield "data: SCRIPT_ERROR\n\n"
            return

        # Security check: Ensure the file to scan is within the UPLOADS_DIR
        if UPLOADS_DIR.resolve() not in resolved_scan_path.parents:
            logger.error(f"Security alert: Attempt to scan file outside of uploads directory: {resolved_scan_path}")
            yield f"data: ERROR: Invalid file path for scanning.\n\n"
            yield "data: SCRIPT_ERROR\n\n"
            return

    except Exception as path_e:
        logger.error(f"Error resolving or validating scan file path '{file_path_to_scan}': {path_e}")
        yield f"data: ERROR: Invalid file path provided for scanning: {path_e}\n\n"
        yield "data: SCRIPT_ERROR\n\n"
        return

    try:
        command = ["python", str(AUTOMATION_SCRIPT_PATH), str(resolved_scan_path)]

        logger.info(f"Starting scan script: {' '.join(command)}")
        yield "data: Scan process starting...\n\n"

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )

        while True:
            if process.stdout is None: break
            line_bytes = await process.stdout.readline()
            if not line_bytes: break
            line = line_bytes.decode('utf-8', errors='replace').strip()
            # Ensure SSE format: each message should be prefixed with "data: " and end with "\n\n"
            yield f"data: {line}\n\n"
            await asyncio.sleep(0.05)

        await process.wait()
        return_code = process.returncode
        logger.info(f"Scan script finished for '{resolved_scan_path.name}' with exit code {return_code}")

        # The script itself is expected to print the final JSON or SCRIPT_DONE/SCRIPT_ERROR
        # No need to add extra SCRIPT_DONE/ERROR here if the script handles it.
        if return_code != 0 and not line.startswith('{"event": "scan_complete"'): # if script failed and didn't send completion
             yield f"data: Script execution failed with code {return_code} (final event might be missing).\n\n"
             yield f"data: SCRIPT_ERROR\n\n"


    except FileNotFoundError:
        logger.error(f"ERROR: Scan script '{AUTOMATION_SCRIPT_PATH}' not found.")
        yield f"data: ERROR: Scan script '{AUTOMATION_SCRIPT_PATH}' not found.\n\n"
        yield "data: SCRIPT_ERROR\n\n"
    except Exception as e:
        logger.error(f"An error occurred during scan script execution: {str(e)}", exc_info=True)
        yield f"data: A server-side error occurred during scan: {str(e)}\n\n"
        yield "data: SCRIPT_ERROR\n\n"
    finally:
        if process and process.returncode is None:
            logger.warning(f"Scan script process for '{file_path_to_scan}' was still running, attempting to terminate.")
            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=5.0)
                logger.info("Scan script process terminated.")
                yield "data: Process was terminated.\n\n"
            except asyncio.TimeoutError:
                logger.error("Failed to terminate scan script process in time, attempting kill.")
                process.kill()
                await process.wait()
                logger.info("Scan script process killed.")
                yield "data: Process was killed due to timeout on termination.\n\n"
            except Exception as e_term:
                logger.error(f"Error during scan script process termination: {e_term}")
                yield f"data: Error during process termination: {e_term}\n\n"


@app.get("/start-scan") # Changed from /run-automation
async def start_scan_stream(request: Request, file_path: str):
    """
    Endpoint to trigger the scan script for a given file_path and stream logs via SSE.
    `file_path` should be the path to the uploaded file.
    """
    logger.info(f"Received /start-scan request for file_path: {file_path}")
    if not file_path:
        raise HTTPException(status_code=400, detail="file_path query parameter is required.")

    # Security: Basic check to ensure file_path is not attempting traversal using ".."
    # More robust validation happens in run_scan_script_and_stream_logs
    if ".." in file_path:
        logger.warning(f"Potential directory traversal attempt in file_path: {file_path}")
        raise HTTPException(status_code=400, detail="Invalid file_path.")

    return StreamingResponse(run_scan_script_and_stream_logs(file_path), media_type="text/event-stream")

@app.get("/download/{filename:path}")
async def download_generated_file(filename: str): # Renamed for clarity
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
