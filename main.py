import os
# import subprocess # No longer needed for local script execution
# import time # May not be needed if not inducing artificial delays
import asyncio
import logging
import shutil
from pathlib import Path
import httpx # For making HTTP requests to the agent

from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse, JSONResponse
# from fastapi.staticfiles import StaticFiles # Not currently used
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
AGENT_URL = "http://172.31.47.28:8000" # Windows VM Agent URL

BASE_DIR = Path(__file__).resolve().parent
HOST_LOG_DIR = BASE_DIR / "host_log_output"  # Main directory for FastAPI server's local storage
UPLOADS_DIR = HOST_LOG_DIR / "uploads"       # Subdirectory for uploads by clients to FastAPI server
# AUTOMATION_SCRIPT_PATH constant is removed as it's no longer used.

# Ensure local directories exist for FastAPI server
HOST_LOG_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
logger.info(f"FastAPI Host log directory: {HOST_LOG_DIR.resolve()}")
logger.info(f"FastAPI Uploads directory: {UPLOADS_DIR.resolve()}")


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

# The local script execution function `run_scan_script_and_stream_logs` has been removed.
# Its functionality is replaced by the agent proxy logic in `/start-scan`.

async def stream_agent_response(agent_url_with_params: str):
    """Helper function to stream SSE data from the agent."""
    try:
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", agent_url_with_params, timeout=None) as response:
                # Check if agent responded with an error before trying to stream
                if response.status_code != 200:
                    error_content = await response.aread()
                    logger.error(f"Agent responded with {response.status_code}: {error_content.decode()}")
                    yield f"data: ERROR: Agent request failed with status {response.status_code} - {error_content.decode()}\n\n"
                    yield f"data: SCRIPT_ERROR\n\n" # Signal error to client
                    return

                async for chunk in response.aiter_bytes():
                    # Agent is expected to send SSE formatted data (data: ...\n\n)
                    # We simply relay these chunks.
                    yield chunk
    except httpx.RequestError as e:
        logger.error(f"HTTPX RequestError connecting to agent at {agent_url_with_params}: {e}")
        yield f"data: ERROR: Could not connect to analysis agent: {type(e).__name__}\n\n"
        yield f"data: SCRIPT_ERROR\n\n"
    except Exception as e:
        logger.error(f"Generic error streaming from agent at {agent_url_with_params}: {e}", exc_info=True)
        yield f"data: ERROR: An unexpected error occurred while streaming from agent.\n\n"
        yield f"data: SCRIPT_ERROR\n\n"

@app.get("/start-scan")
async def start_scan_proxy(request: Request, file_path: str): # file_path is local to FastAPI server
    """
    Uploads the specified local file to the agent, then proxies the scan request
    to the Windows agent and streams back its SSE output.
    """
    logger.info(f"Received /start-scan request for FastAPI local file_path: {file_path}")
    if not file_path:
        raise HTTPException(status_code=400, detail="file_path query parameter is required.")

    local_file_to_upload = Path(file_path)
    if not local_file_to_upload.is_file():
        logger.error(f"File not found locally on FastAPI server: {file_path}")
        raise HTTPException(status_code=404, detail=f"File not found on server: {local_file_to_upload.name}")

    # Ensure the file is within the UPLOADS_DIR for security
    if UPLOADS_DIR.resolve() not in local_file_to_upload.resolve().parents:
        logger.error(f"Security alert: Attempt to access file outside of uploads directory for agent upload: {local_file_to_upload.resolve()}")
        raise HTTPException(status_code=403, detail="Access to specified file path is forbidden.")

    original_filename = local_file_to_upload.name
    agent_receive_file_url = f"{AGENT_URL}/receive-file" # Agent needs this endpoint
    agent_run_automation_url = f"{AGENT_URL}/run-automation" # Agent's SSE endpoint

    try:
        async with httpx.AsyncClient() as client:
            logger.info(f"Attempting to upload '{original_filename}' to agent at {agent_receive_file_url}")

            # Step 1: Send the file to the agent
            files = {'file': (original_filename, local_file_to_upload.open('rb'), 'application/octet-stream')}
            try:
                upload_response = await client.post(agent_receive_file_url, files=files, timeout=30.0) # 30s timeout for upload
                upload_response.raise_for_status() # Raises HTTPStatusError for 4xx/5xx responses

                agent_file_info = upload_response.json()
                # Assuming agent returns JSON like {"message": "...", "agent_file_path": "C:/path/on/agent/file.exe"}
                # or at least confirms the filename it will use.
                # For this example, we'll assume the agent uses the same filename in a predefined location.
                # The crucial part is what `file_path` the agent's /run-automation expects.
                # We will pass the original_filename, assuming the agent knows where to find it after /receive-file.
                logger.info(f"File '{original_filename}' successfully uploaded to agent. Agent response: {agent_file_info}")

                # The agent_file_path_for_scan should be what the agent's /run-automation endpoint expects.
                # If the agent stores it by original_filename in a specific dir, then original_filename is fine.
                # If agent returns a specific path, use that.
                # For now, we use original_filename.
                agent_file_path_for_scan_param = original_filename

            except httpx.RequestError as e:
                logger.error(f"Error uploading file to agent at {agent_receive_file_url}: {e}")
                # Stream an error back to the client immediately
                async def error_stream_upload():
                    yield f"data: ERROR: Could not upload file to analysis agent: {type(e).__name__}\n\n"
                    yield f"data: SCRIPT_ERROR\n\n"
                return StreamingResponse(error_stream_upload(), media_type="text/event-stream")
            except httpx.HTTPStatusError as e:
                logger.error(f"Agent returned error during file upload ({agent_receive_file_url}): {e.response.status_code} - {e.response.text}")
                async def error_stream_upload_status():
                    yield f"data: ERROR: Agent rejected file upload: {e.response.status_code} - {e.response.text}\n\n"
                    yield f"data: SCRIPT_ERROR\n\n"
                return StreamingResponse(error_stream_upload_status(), media_type="text/event-stream")

            # Step 2: If upload successful, trigger scan on agent and stream SSE response
            logger.info(f"File uploaded. Now triggering scan on agent: {agent_run_automation_url}?file_path={agent_file_path_for_scan_param}")
            # The stream_agent_response helper will handle streaming and further errors.
            return StreamingResponse(stream_agent_response(f"{agent_run_automation_url}?file_path={agent_file_path_for_scan_param}"), media_type="text/event-stream")

    except Exception as e:
        logger.error(f"Outer error in /start-scan for {original_filename}: {e}", exc_info=True)
        # This catches errors before even starting the streaming part, e.g., if local file read fails.
        async def error_stream_generic():
            yield f"data: ERROR: An unexpected server error occurred before contacting agent: {type(e).__name__}.\n\n"
            yield f"data: SCRIPT_ERROR\n\n"
        return StreamingResponse(error_stream_generic(), media_type="text/event-stream")


@app.get("/download/{filename:path}")
async def download_generated_file(filename: str):
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
