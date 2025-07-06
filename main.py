from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import os, uuid, subprocess, json, shutil
import configparser

# Load configuration from config.ini
config = configparser.ConfigParser()
config_file_path = 'config.ini'

if not os.path.exists(config_file_path):
    print(f"Error: config.ini not found at {config_file_path}")
    # Fallback to default values or exit
    MAX_FILE_SIZE_MB = 50
    MAX_DURATION_SECONDS = 600
else:
    config.read(config_file_path)
    try:
        MAX_FILE_SIZE_MB = config.getint('LIMITS', 'MAX_FILE_SIZE_MB')
        MAX_DURATION_SECONDS = config.getint('LIMITS', 'MAX_DURATION_SECONDS')
        print(f"Configuration loaded: MAX_FILE_SIZE_MB={MAX_FILE_SIZE_MB}, MAX_DURATION_SECONDS={MAX_DURATION_SECONDS}")
    except (configparser.NoSectionError, configparser.NoOptionError, ValueError) as e:
        print(f"Error reading configuration from config.ini: {e}")
        print("Using default values for limits.")
        MAX_FILE_SIZE_MB = 50
        MAX_DURATION_SECONDS = 600

def replace_slash_with_underscore(filename):
    return filename.replace("/", "_")

def get_audio_duration(filepath):
    try:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", filepath]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except subprocess.CalledProcessError as e:
        print(f"Error getting duration for {filepath}: {e.stderr}")
        return None
    except ValueError:
        print(f"Could not parse duration for {filepath}")
        return None

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"

# Clean up and create directories
for directory in [UPLOAD_DIR, OUTPUT_DIR]:
    if os.path.exists(directory):
        shutil.rmtree(directory)
    os.makedirs(directory, exist_ok=True)

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request,
                                                    "MAX_FILE_SIZE_MB": MAX_FILE_SIZE_MB,
                                                    "MAX_DURATION_SECONDS": MAX_DURATION_SECONDS})

@app.post("/upload")
async def upload(request: Request, file: UploadFile = File(None), youtube_url: str = Form(None)):
    input_path = None
    basename = None
    spleeter_result_dir = None
    vocal_mp3_path = None
    inst_mp3_path = None
    try:
        if file and file.filename:
            # File Upload Logic
            file_size_mb = file.size / (1024 * 1024)
            if file_size_mb > MAX_FILE_SIZE_MB:
                return templates.TemplateResponse("index.html", {"request": request, "error": f"파일 크기가 너무 큽니다. 최대 {MAX_FILE_SIZE_MB}MB까지 허용됩니다."})

            basename = os.path.splitext(file.filename)[0]
            input_path = f"{UPLOAD_DIR}/{file.filename}"
            with open(input_path, "wb") as f:
                f.write(await file.read())
            
            duration = get_audio_duration(input_path)
            if duration is None or duration > MAX_DURATION_SECONDS:
                os.remove(input_path) # Clean up the uploaded file
                return templates.TemplateResponse("index.html", {"request": request, "error": f"오디오 길이가 너무 깁니다. 최대 {MAX_DURATION_SECONDS}초까지 허용됩니다."})

        elif youtube_url:
            # YouTube URL Logic
            try:
                # Get YouTube video info to check duration
                yt_dlp_info_cmd = ["yt-dlp", "--dump-json", youtube_url]
                proc_info = subprocess.run(yt_dlp_info_cmd, capture_output=True, text=True, check=True)
                video_info = json.loads(proc_info.stdout)
                
                duration = video_info.get("duration")
                if duration is None or duration > MAX_DURATION_SECONDS:
                    return templates.TemplateResponse("index.html", {"request": request, "error": f"YouTube 영상 길이가 너무 깁니다. 최대 {MAX_DURATION_SECONDS}초까지 허용됩니다."})
                
                # Use yt-dlp to get video title as basename and download audio
                basename = replace_slash_with_underscore(video_info.get("title", "downloaded_audio"))
                input_path = f"{UPLOAD_DIR}/{basename}.mp3"
                subprocess.run(["yt-dlp", "-x", "--audio-format", "mp3", "-o", input_path, youtube_url], check=True)

                # Check file size after download for YouTube videos
                file_size_mb = os.path.getsize(input_path) / (1024 * 1024)
                if file_size_mb > MAX_FILE_SIZE_MB:
                    os.remove(input_path) # Clean up the downloaded file
                    return templates.TemplateResponse("index.html", {"request": request, "error": f"다운로드된 파일 크기가 너무 큽니다. 최대 {MAX_FILE_SIZE_MB}MB까지 허용됩니다."})

            except subprocess.CalledProcessError as e:
                return templates.TemplateResponse("index.html", {"request": request, "error": f"YouTube URL 처리 중 오류: {e.stderr.strip() if e.stderr else e}"})
            except json.JSONDecodeError:
                return templates.TemplateResponse("index.html", {"request": request, "error": "YouTube 영상 정보를 가져오는 데 실패했습니다."})

        else:
            return templates.TemplateResponse("index.html", {"request": request, "error": "파일을 업로드하거나 YouTube URL을 제공해주세요."})

        # Display message for YouTube download
        if youtube_url:
            # This message will be displayed, but the process will continue
            print("유투브에서 음원을 추출 중...")

        # Spleeter and FFmpeg processing (existing logic)
        # Display message for audio separation
        print("오디오 분리 작업중...")
        subprocess.run(["spleeter", "separate", "-o", OUTPUT_DIR, "-p", "spleeter:2stems", input_path], check=True)

        spleeter_result_dir = f"{OUTPUT_DIR}/{basename}"
        vocal_wav_path = f"{spleeter_result_dir}/vocals.wav"
        inst_wav_path = f"{spleeter_result_dir}/accompaniment.wav"
        vocal_mp3_path = f"{OUTPUT_DIR}/{basename}/{basename}_Vocal.mp3"
        inst_mp3_path = f"{OUTPUT_DIR}/{basename}/{basename}_Inst.mp3"

        # Convert WAV to MP3
        subprocess.run(["ffmpeg", "-i", vocal_wav_path, vocal_mp3_path], check=True)
        subprocess.run(["ffmpeg", "-i", inst_wav_path, inst_mp3_path], check=True)

        # Clean up intermediate WAV files
        os.remove(vocal_wav_path)
        os.remove(inst_wav_path)

        return templates.TemplateResponse("index.html", {
            "request": request,
            "vocal_url": f"/download?f={basename}&t=v",
            "inst_url": f"/download?f={basename}&t=a",
            "original_url": f"/download?f={basename}&t=o", # Add original file URL
            "status_message": "오디오 분리 완료!"
        })
    except subprocess.CalledProcessError as e:
        # Clean up input file if spleeter/ffmpeg fails
        if input_path and os.path.exists(input_path):
            os.remove(input_path)
        return templates.TemplateResponse("index.html", {
            "request": request,
            "error": f"오디오 분리 중 오류가 발생했습니다: {e.stderr.strip() if e.stderr else e}"
        })
    except Exception as e:
        # Catch any other unexpected errors
        if input_path and os.path.exists(input_path):
            os.remove(input_path)
        return templates.TemplateResponse("index.html", {
            "request": request,
            "error": f"예상치 못한 오류가 발생했습니다: {e}"
        })

@app.get("/download")
def download(f: str, t: str):
    if t == "v":
        filename = f"{f}_Vocal.mp3"
        filepath = f"{OUTPUT_DIR}/{f}/{filename}"
    elif t == "a":
        filename = f"{f}_Inst.mp3"
        filepath = f"{OUTPUT_DIR}/{f}/{filename}"
    elif t == "o":
        # Assuming original files are in UPLOAD_DIR and are mp3
        filename = f"{f}.mp3"
        filepath = f"{UPLOAD_DIR}/{filename}"
    else:
        return {"error": "Invalid file type"}
    
    return FileResponse(filepath, media_type="audio/mpeg", filename=filename)