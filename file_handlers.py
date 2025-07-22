import os
import time
import uuid
from typing import Optional, Tuple
from fastapi import UploadFile
from fastapi.templating import Jinja2Templates

from audio_utils import (
    get_audio_duration, get_youtube_video_info, download_youtube_audio,
    sanitize_filename, cleanup_file, separate_audio_with_spleeter,
    convert_wav_to_mp3
)
from logger import app_logger


def validate_file_upload(file: UploadFile, max_size_mb: int, max_duration: int, upload_dir: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Validate and save uploaded file.
    Returns: (input_path, basename, error_message)
    """
    try:
        # Check file size
        file_size_mb = file.size / (1024 * 1024)
        if file_size_mb > max_size_mb:
            app_logger.warning(f"File size too large: {file_size_mb:.2f}MB > {max_size_mb}MB")
            return None, None, f"파일 크기가 너무 큽니다. 최대 {max_size_mb}MB까지 허용됩니다."
        
        # Save file with UUID to prevent conflicts
        original_basename = os.path.splitext(file.filename)[0]
        safe_basename = sanitize_filename(original_basename)
        unique_id = uuid.uuid4().hex[:8]
        basename = f"{safe_basename}_{unique_id}"
        
        # Use original extension
        file_ext = os.path.splitext(file.filename)[1]
        unique_filename = f"{basename}{file_ext}"
        input_path = os.path.join(upload_dir, unique_filename)
        
        with open(input_path, "wb") as f:
            f.write(file.file.read())
        
        app_logger.info(f"File uploaded: {file.filename} ({file_size_mb:.2f}MB)")
        
        # Check duration
        duration = get_audio_duration(input_path)
        if duration is None or duration > max_duration:
            cleanup_file(input_path)
            app_logger.warning(f"Audio duration too long: {duration}s > {max_duration}s")
            return None, None, f"오디오 길이가 너무 깁니다. 최대 {max_duration}초까지 허용됩니다."
        
        app_logger.info(f"File validation successful: {basename} ({duration:.2f}s)")
        return input_path, basename, None
        
    except Exception as e:
        app_logger.error(f"File validation error: {e}")
        return None, None, f"파일 처리 중 오류가 발생했습니다: {e}"


def validate_youtube_url(youtube_url: str, max_size_mb: int, max_duration: int, upload_dir: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Validate and download YouTube URL.
    Returns: (input_path, basename, error_message)
    """
    try:
        # Get video info
        video_info, error = get_youtube_video_info(youtube_url)
        if error:
            app_logger.error(f"YouTube info error: {error}")
            return None, None, error
        
        # Check duration
        duration = video_info.get("duration")
        if duration is None or duration > max_duration:
            app_logger.warning(f"YouTube video duration too long: {duration}s > {max_duration}s")
            return None, None, f"YouTube 영상 길이가 너무 깁니다. 최대 {max_duration}초까지 허용됩니다."
        
        # Download audio - let yt-dlp use its own filename first, then get actual title
        temp_basename = f"youtube_temp_{int(time.time())}"
        temp_input_path = os.path.join(upload_dir, f"{temp_basename}.mp3")
        
        download_start_time = time.time()
        app_logger.info(f"Starting YouTube download to temp file: {temp_basename}")
        download_error = download_youtube_audio(youtube_url, temp_input_path)
        download_end_time = time.time()
        download_time = download_end_time - download_start_time

        if download_error:
            app_logger.error(f"YouTube download error: {download_error}")
            return None, None, download_error
        
        # Get video title and create meaningful filename
        video_title = video_info.get("title", "downloaded_audio")
        
        # Extract video ID from URL for better naming
        video_id = None
        if 'youtu.be/' in youtube_url:
            video_id = youtube_url.split('youtu.be/')[-1].split('?')[0]
        elif 'watch?v=' in youtube_url:
            video_id = youtube_url.split('watch?v=')[-1].split('&')[0]
        
        # Create a better filename with UUID to prevent conflicts
        unique_id = uuid.uuid4().hex[:8]
        
        if video_title and video_title != "downloaded_audio" and "youtube video" not in video_title.lower():
            # We got a proper title
            safe_title = sanitize_filename(video_title)
            basename = f"{safe_title}_{unique_id}"
            app_logger.info(f"Using extracted title: {video_title}")
        elif video_id:
            # Use video ID with a descriptive name
            basename = f"YouTube_Video_{video_id}_{unique_id}"
            app_logger.info(f"Using video ID as filename: {basename}")
        else:
            # Fallback to timestamp
            basename = f"youtube_video_{int(time.time())}_{unique_id}"
            app_logger.info(f"Using timestamp as filename: {basename}")
        final_input_path = os.path.join(upload_dir, f"{basename}.mp3")
        
        # Rename temp file to final filename
        if os.path.exists(temp_input_path):
            os.rename(temp_input_path, final_input_path)
            app_logger.info(f"Renamed temp file to: {basename}.mp3")
        
        app_logger.info(f"YouTube download took {download_time:.2f} seconds.")
        
        # Check file size after download
        if not os.path.exists(final_input_path):
            app_logger.error(f"Downloaded file not found at: {final_input_path}")
            return None, None, "다운로드된 파일을 찾을 수 없습니다."
            
        file_size_mb = os.path.getsize(final_input_path) / (1024 * 1024)
        if file_size_mb > max_size_mb:
            cleanup_file(final_input_path)
            app_logger.warning(f"Downloaded file too large: {file_size_mb:.2f}MB > {max_size_mb}MB")
            return None, None, f"다운로드된 파일 크기가 너무 큽니다. 최대 {max_size_mb}MB까지 허용됩니다."
        
        app_logger.info(f"YouTube download successful: {basename} ({file_size_mb:.2f}MB, {duration:.2f}s)")
        return final_input_path, basename, None
        
    except Exception as e:
        app_logger.error(f"YouTube processing error: {e}")
        return None, None, f"YouTube URL 처리 중 예상치 못한 오류: {e}"


def process_audio_separation(input_path: str, basename: str, output_dir: str, spleeter_model: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Process audio separation and conversion.
    Returns: (vocal_mp3_path, inst_mp3_path, error_message)
    """
    try:
        spleeter_result_dir = os.path.join(output_dir, basename)
        os.makedirs(spleeter_result_dir, exist_ok=True)
        app_logger.info(f"Created Spleeter output directory: {spleeter_result_dir}")

        # Separate audio with Spleeter
        error = separate_audio_with_spleeter(input_path, output_dir, spleeter_model)
        if error:
            app_logger.error(f"Spleeter error: {error}")
            return None, None, error
        
        # Set up file paths
        vocal_wav_path = os.path.join(spleeter_result_dir, "vocals.wav")
        inst_wav_path = os.path.join(spleeter_result_dir, "accompaniment.wav")
        vocal_mp3_path = os.path.join(spleeter_result_dir, f"{basename}_Vocal.mp3")
        inst_mp3_path = os.path.join(spleeter_result_dir, f"{basename}_Inst.mp3")

        # Check if WAV files exist before conversion
        if not os.path.exists(vocal_wav_path):
            error_msg = f"Vocal WAV file not found at {vocal_wav_path}"
            app_logger.error(error_msg)
            return None, None, error_msg
        if not os.path.exists(inst_wav_path):
            error_msg = f"Instrumental WAV file not found at {inst_wav_path}"
            app_logger.error(error_msg)
            return None, None, error_msg

        # Convert WAV to MP3
        vocal_error = convert_wav_to_mp3(vocal_wav_path, vocal_mp3_path)
        if vocal_error:
            app_logger.error(f"Vocal conversion error: {vocal_error}")
            return None, None, vocal_error
        
        inst_error = convert_wav_to_mp3(inst_wav_path, inst_mp3_path)
        if inst_error:
            app_logger.error(f"Instrumental conversion error: {inst_error}")
            return None, None, inst_error
        
        # Clean up intermediate WAV files
        cleanup_file(vocal_wav_path)
        cleanup_file(inst_wav_path)
        
        app_logger.info(f"Audio separation completed for: {basename}")
        return vocal_mp3_path, inst_mp3_path, None
        
    except Exception as e:
        app_logger.error(f"Audio processing error: {e}")
        return None, None, f"오디오 분리 중 예상치 못한 오류: {e}"