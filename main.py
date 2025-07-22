from fastapi import FastAPI, Request, UploadFile, File, Form, Query, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from urllib.parse import unquote, quote
import os
import shutil
import time
import re
from typing import Optional, Tuple

from config_manager import config_manager
from audio_utils import (
    sanitize_filename, get_audio_duration, get_youtube_video_info,
    download_youtube_audio, separate_audio_with_spleeter, convert_wav_to_mp3,
    cleanup_files
)
from logger import app_logger

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Get configuration
UPLOAD_DIR = config_manager.get_upload_dir()
OUTPUT_DIR = config_manager.get_output_dir()
MAX_FILE_SIZE_MB = config_manager.get_max_file_size_mb()
MAX_DURATION_SECONDS = config_manager.get_max_duration_seconds()

app_logger.info(f"Configuration: MAX_FILE_SIZE_MB={MAX_FILE_SIZE_MB}, MAX_DURATION_SECONDS={MAX_DURATION_SECONDS}")
app_logger.info(f"Directories: UPLOAD_DIR={UPLOAD_DIR}, OUTPUT_DIR={OUTPUT_DIR}")

# Clean up and create directories
for directory in [UPLOAD_DIR, OUTPUT_DIR]:
    if os.path.exists(directory):
        # .gitkeep 파일을 제외하고 모든 파일 삭제
        for filename in os.listdir(directory):
            if filename != '.gitkeep':
                file_path = os.path.join(directory, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
        app_logger.info(f"Cleaned up directory: {directory}")
    else:
        os.makedirs(directory, exist_ok=True)
        app_logger.info(f"Created directory: {directory}")

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request,
                                                    "MAX_FILE_SIZE_MB": MAX_FILE_SIZE_MB,
                                                    "MAX_DURATION_SECONDS": MAX_DURATION_SECONDS})

from file_handlers import validate_file_upload, validate_youtube_url, process_audio_separation
from task_manager import task_manager, TaskStatus

@app.post("/upload")
async def upload(request: Request, background_tasks: BackgroundTasks, 
                file: UploadFile = File(None), youtube_url: str = Form(None)):
    """Handle file upload or YouTube URL processing for audio separation."""
    
    try:
        # Basic validation only
        if not file or not file.filename:
            if not youtube_url:
                app_logger.warning("No file or YouTube URL provided")
                return JSONResponse(
                    status_code=400,
                    content={"error": "파일을 업로드하거나 YouTube URL을 제공해주세요."}
                )
        
        # Create task immediately with minimal info
        task_id = task_manager.create_task_immediate()
        
        # Try to submit task for processing
        if not task_manager.submit_task_with_input(task_id, file, youtube_url, MAX_FILE_SIZE_MB, MAX_DURATION_SECONDS, UPLOAD_DIR):
            # Task queue is full
            return JSONResponse(
                status_code=503,
                content={"error": "서버가 바쁩니다. 잠시 후 다시 시도해주세요."}
            )
        
        app_logger.info(f"Created immediate background task {task_id}")
        
        # Return task_id immediately - no template rendering
        return JSONResponse(content={
            "task_id": task_id,
            "message": "음성 분리 작업을 시작했습니다."
        })
        
    except Exception as e:
        app_logger.error(f"Unexpected error during upload processing: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"예상치 못한 오류가 발생했습니다: {e}"}
        )

@app.get("/api/task/{task_id}")
async def get_task_status(task_id: str):
    """Get task status and progress."""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return JSONResponse(content=task.to_dict())

@app.get("/api/stats")
async def get_stats():
    """Get task manager statistics."""
    return JSONResponse(content=task_manager.get_stats())

@app.post("/api/cleanup")
async def cleanup_old_tasks():
    """Clean up old tasks (admin endpoint)."""
    task_manager.cleanup_old_tasks()
    return JSONResponse(content={"message": "Cleanup completed"})

@app.get("/download")
def download(
    f: str = Query(..., description="Filename without extension"),
    t: str = Query(..., pattern="^[vao]$", description="File type: v=vocal, a=accompaniment, o=original")
):
    """Handle file downloads for separated audio files."""
    
    try:
        # Decode URL-encoded filename and validate
        try:
            clean_filename = unquote(f, encoding='utf-8').strip()
        except:
            # If UTF-8 decoding fails, try other encodings or use original
            try:
                clean_filename = unquote(f, encoding='cp949').strip()  # Korean encoding
            except:
                clean_filename = f.strip()
        
        if not clean_filename:
            app_logger.warning("Empty filename parameter after decoding")
            raise HTTPException(status_code=400, detail="Invalid filename parameter")
        
        app_logger.info(f"Download request - filename: '{clean_filename}', type: '{t}'")
        
        # Build file paths based on type
        if t == "v":
            filename = f"{clean_filename}_Vocal.mp3"
            filepath = os.path.join(OUTPUT_DIR, clean_filename, filename)
        elif t == "a":
            filename = f"{clean_filename}_Inst.mp3"
            filepath = os.path.join(OUTPUT_DIR, clean_filename, filename)
        elif t == "o":
            filename = f"{clean_filename}.mp3"
            filepath = os.path.join(UPLOAD_DIR, filename)
        
        app_logger.info(f"Looking for file at: {filepath}")
        
        # Check if file exists
        if not os.path.exists(filepath):
            app_logger.error(f"File not found: {filepath}")
            
            # Debug: List directory contents and try to find similar files
            if t in ["v", "a"]:
                output_subdir = os.path.join(OUTPUT_DIR, clean_filename)
                if os.path.exists(output_subdir):
                    files_in_dir = os.listdir(output_subdir)
                    app_logger.info(f"Files in {output_subdir}: {files_in_dir}")
                    
                    # Try to find the file with similar name pattern
                    target_suffix = "_Vocal.mp3" if t == "v" else "_Inst.mp3"
                    for file_in_dir in files_in_dir:
                        if file_in_dir.endswith(target_suffix):
                            actual_filepath = os.path.join(output_subdir, file_in_dir)
                            app_logger.info(f"Found similar file: {actual_filepath}")
                            filepath = actual_filepath
                            filename = file_in_dir
                            break
                else:
                    app_logger.info(f"Output subdirectory does not exist: {output_subdir}")
                    # Try to find directory with similar name
                    if os.path.exists(OUTPUT_DIR):
                        all_dirs = os.listdir(OUTPUT_DIR)
                        app_logger.info(f"Available output directories: {all_dirs}")
                        
            elif t == "o":
                if os.path.exists(UPLOAD_DIR):
                    files_in_upload = os.listdir(UPLOAD_DIR)
                    app_logger.info(f"Files in {UPLOAD_DIR}: {files_in_upload}")
                    
                    # Try to find the original file
                    for file_in_upload in files_in_upload:
                        if file_in_upload.endswith('.mp3') and clean_filename in file_in_upload:
                            actual_filepath = os.path.join(UPLOAD_DIR, file_in_upload)
                            app_logger.info(f"Found original file: {actual_filepath}")
                            filepath = actual_filepath
                            filename = file_in_upload
                            break
            
            # Final check if we found an alternative file
            if not os.path.exists(filepath):
                raise HTTPException(status_code=404, detail="File not found")
        
        app_logger.info(f"Serving download: {filename}")
        
        # Create a simple ASCII-safe filename for Content-Disposition
        safe_filename = "audio_download.mp3"
        
        return FileResponse(
            filepath, 
            media_type="audio/mpeg", 
            filename=safe_filename
        )
        
    except HTTPException:
        raise
    except Exception as e:
        app_logger.error(f"Download error: {e}")
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

# Railway 배포용 서버 시작
if __name__ == "__main__":
    import os
    import uvicorn
    
    # Railway에서 제공하는 PORT 환경변수 사용
    port = int(os.getenv("PORT", 8000))
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,  # 프로덕션에서는 reload 비활성화
        access_log=True
    )