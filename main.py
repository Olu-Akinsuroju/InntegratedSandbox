import os
import asyncio
import logging
import shutil
from pathlib import Path
import httpx

from fastapi import FastAPI, Request, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

AGENT_URL = "http://13.51.207.164:8000" # Windows VM Agent URL Updated

BASE_DIR = Path(__file__).resolve().parent
HOST_LOG_DIR = BASE_DIR / "host_log_output"
UPLOADS_DIR = HOST_LOG_DIR / "uploads"

HOST_LOG_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
logger.info(f"FastAPI Host log directory: {HOST_LOG_DIR.resolve()}")
logger.info(f"FastAPI Uploads directory: {UPLOADS_DIR.resolve()}")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload")
async def upload_file_for_scan(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided or filename is empty.")

    safe_filename = Path(file.filename).name
    if not safe_filename:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    temp_file_path = UPLOADS_DIR / safe_filename

    try:
        with temp_file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info(f"File '{safe_filename}' uploaded successfully to '{temp_file_path}'.")
        return JSONResponse(content={"message": "File uploaded successfully", "filePath": str(temp_file_path.resolve())})
    except Exception as e:
        logger.error(f"Error saving uploaded file '{safe_filename}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Could not save file: {str(e)}")
    finally:
        await file.close()

async def stream_agent_response(agent_url_with_params: str):
    try:
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", agent_url_with_params, timeout=None) as response:
                if response.status_code != 200:
                    error_content = await response.aread()
                    logger.error(f"Agent responded with {response.status_code}: {error_content.decode()}")
                    yield f"data: ERROR: Agent request failed with status {response.status_code} - {error_content.decode()}\n\n"
                    yield f"data: SCRIPT_ERROR\n\n"
                    return

                async for chunk in response.aiter_bytes():
                    yield chunk
    except httpx.RequestError as e:
        logger.error(f"HTTPX RequestError connecting to agent at {agent_url_with_params}: {e}")
        error_type = type(e).__name__
        # This is tricky. We are in an async generator. We can't 'return' a StreamingResponse here.
        # We must yield the error messages.
        yield f"data: ERROR: Could not connect to analysis agent: {error_type}\n\n"
        yield f"data: SCRIPT_ERROR\n\n"
        # The caller will wrap this generator in a StreamingResponse.
    except Exception as e:
        logger.error(f"Generic error streaming from agent at {agent_url_with_params}: {e}", exc_info=True)
        yield f"data: ERROR: An unexpected error occurred while streaming from agent.\n\n"
        yield f"data: SCRIPT_ERROR\n\n"
        # The caller will wrap this generator in a StreamingResponse.


@app.get("/start-scan")
async def start_scan_proxy(request: Request, file_path: str):
    logger.info(f"Received /start-scan request for FastAPI local file_path: {file_path}")
    if not file_path:
        raise HTTPException(status_code=400, detail="file_path query parameter is required.")

    local_file_to_upload = Path(file_path)
    if not local_file_to_upload.is_file():
        logger.error(f"File not found locally on FastAPI server: {file_path}")
        raise HTTPException(status_code=404, detail=f"File not found on server: {local_file_to_upload.name}")

    if UPLOADS_DIR.resolve() not in local_file_to_upload.resolve().parents:
        logger.error(f"Security alert: Attempt to access file outside of uploads directory for agent upload: {local_file_to_upload.resolve()}")
        raise HTTPException(status_code=403, detail="Access to specified file path is forbidden.")

    original_filename = local_file_to_upload.name
    agent_receive_file_url = f"{AGENT_URL}/receive-file"
    agent_run_automation_url = f"{AGENT_URL}/run-automation"

    # This outer try-except is for errors before we start streaming (e.g., initial file read)
    # Errors during POST or GET streaming will be handled by yielding error data within the stream.
    try:
        async with httpx.AsyncClient() as client:
            logger.info(f"Attempting to upload '{original_filename}' to agent at {agent_receive_file_url}")
            files = {'file': (original_filename, local_file_to_upload.open('rb'), 'application/octet-stream')}

            try:
                upload_response = await client.post(agent_receive_file_url, files=files, timeout=30.0)
                upload_response.raise_for_status() # Check for 4xx/5xx errors from agent
                # agent_file_info = upload_response.json() # Assuming agent sends back JSON
                # logger.info(f"File '{original_filename}' successfully uploaded to agent. Agent response: {agent_file_info}")
                logger.info(f"File '{original_filename}' successfully uploaded to agent.")
                # For now, assume agent uses original_filename in its known location
                agent_file_path_for_scan_param = original_filename

            except httpx.RequestError as e:
                logger.error(f"Error uploading file to agent at {agent_receive_file_url}: {e}")
                error_type = type(e).__name__
                async def error_stream_upload_request():
                    yield f"data: ERROR: Could not upload file to analysis agent: {error_type}\n\n"
                    yield f"data: SCRIPT_ERROR\n\n"
                return StreamingResponse(error_stream_upload_request(), media_type="text/event-stream")

            except httpx.HTTPStatusError as e:
                logger.error(f"Agent returned HTTP error during file upload ({agent_receive_file_url}): {e.response.status_code} - {e.response.text}")
                status = e.response.status_code
                text = e.response.text
                async def error_stream_upload_status():
                    yield f"data: ERROR: Agent rejected file upload: {status} - {text}\n\n"
                    yield f"data: SCRIPT_ERROR\n\n"
                return StreamingResponse(error_stream_upload_status(), media_type="text/event-stream")

            # If upload was successful, proceed to trigger scan and stream response
            logger.info(f"File uploaded. Now triggering scan on agent: {agent_run_automation_url}?file_path={agent_file_path_for_scan_param}")
            # stream_agent_response is an async generator. We directly pass it to StreamingResponse.
            return StreamingResponse(stream_agent_response(f"{agent_run_automation_url}?file_path={agent_file_path_for_scan_param}"), media_type="text/event-stream")

    except Exception as e: # Catches errors like local_file_to_upload.open('rb') if file is gone
        logger.error(f"Outer error in /start-scan for {original_filename} before agent communication: {e}", exc_info=True)
        error_type = type(e).__name__
        async def error_stream_generic():
            yield f"data: ERROR: An unexpected server error occurred: {error_type}.\n\n"
            yield f"data: SCRIPT_ERROR\n\n"
        return StreamingResponse(error_stream_generic(), media_type="text/event-stream")

@app.get("/download/{filename:path}")
async def download_generated_file(filename: str):
    logger.info(f"Download request for file: {filename} from directory: {HOST_LOG_DIR}")

    host_log_dir_abs = os.path.abspath(HOST_LOG_DIR) # Should be Path(HOST_LOG_DIR).resolve()
    # Ensure filename is just a name, not a path itself, for security when joining
    safe_basename = Path(filename).name
    requested_file_path = Path(HOST_LOG_DIR) / safe_basename # Use Path objects for joining

    # Resolve to absolute path for comparison
    resolved_requested_path = requested_file_path.resolve()
    resolved_host_log_dir = Path(HOST_LOG_DIR).resolve()

    if not str(resolved_requested_path).startswith(str(resolved_host_log_dir)):
        logger.warning(f"Directory traversal attempt blocked for: {filename}. Resolved: {resolved_requested_path}")
        raise HTTPException(status_code=403, detail="Access denied: Invalid file path.")

    if not resolved_requested_path.is_file(): # is_file also checks existence
        logger.error(f"File not found: {resolved_requested_path}")
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")

    return FileResponse(str(resolved_requested_path), media_type='application/octet-stream', filename=safe_basename)

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting Uvicorn server locally. HOST_LOG_DIR is {HOST_LOG_DIR.resolve()}")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
