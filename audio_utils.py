import os
import subprocess
import json
import sys
import re
import urllib.request
from typing import Optional, Tuple


def sanitize_filename(filename: str) -> str:
    """Clean filename by removing/replacing problematic characters."""
    import re
    
    # Remove or replace problematic characters
    # First handle common replacements
    replacements = {
        '/': '_',
        '\\': '_',
        ':': '-',
        '*': '_',
        '?': '',
        '"': "'",
        '<': '(',
        '>': ')',
        '|': '_',
        '\n': ' ',
        '\r': ' ',
        '\t': ' '
    }
    
    # Apply replacements
    for old, new in replacements.items():
        filename = filename.replace(old, new)
    
    # Remove multiple spaces and trim
    filename = re.sub(r'\s+', ' ', filename.strip())
    
    # Remove leading/trailing dots and spaces
    filename = filename.strip('. ')
    
    # Limit length to avoid filesystem issues
    if len(filename) > 200:
        filename = filename[:200].strip()
    
    # Ensure we have a valid filename
    if not filename or filename in ('', '.', '..'):
        filename = 'downloaded_audio'
    
    return filename


def get_audio_duration(filepath: str) -> Optional[float]:
    """Get audio duration in seconds using ffprobe."""
    try:
        cmd = [
            "ffprobe", "-v", "error", 
            "-show_entries", "format=duration", 
            "-of", "default=noprint_wrappers=1:nokey=1", 
            filepath
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except FileNotFoundError:
        print("Error: ffprobe command not found. Please ensure ffmpeg is installed and in your PATH.")
        return None
    except subprocess.CalledProcessError as e:
        print(f"Error getting duration for {filepath}: {e.stderr}")
        return None
    except ValueError:
        print(f"Could not parse duration for {filepath}")
        return None


def get_youtube_title_from_web(url: str) -> Optional[str]:
    """Extract YouTube title by parsing the webpage HTML."""
    try:
        # Clean URL to standard format
        video_id = None
        if 'youtu.be/' in url:
            video_id = url.split('youtu.be/')[-1].split('?')[0]
        elif 'watch?v=' in url:
            video_id = url.split('watch?v=')[-1].split('&')[0]
        
        if not video_id:
            return None
            
        # Try YouTube oEmbed API first (most reliable)
        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        
        try:
            req = urllib.request.Request(
                oembed_url,
                headers={'User-Agent': 'Mozilla/5.0 (compatible; YouTube Title Fetcher)'}
            )
            
            with urllib.request.urlopen(req, timeout=10) as response:
                content = response.read().decode('utf-8', errors='replace')
                data = json.loads(content)
                title = data.get('title')
                
                if title and len(title) > 3:
                    print(f"Got title from oEmbed: {title}")
                    return title
                    
        except Exception as e:
            print(f"oEmbed failed: {e}")
        
        # HTML fallback
        try:
            req = urllib.request.Request(
                f"https://www.youtube.com/watch?v={video_id}",
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            )
            
            with urllib.request.urlopen(req, timeout=10) as response:
                content = response.read().decode('utf-8', errors='ignore')
            
            match = re.search(r'<title>([^<]+)</title>', content, re.IGNORECASE)
            if match:
                title = match.group(1).replace(' - YouTube', '').strip()
                if title and len(title) > 3 and title != video_id:
                    return title
                        
        except Exception:
            pass  # Silent fallback failure
        
        return None
        
    except Exception as e:
        print(f"Failed to extract title from web: {e}")
        return None


def get_youtube_video_info(url: str) -> Tuple[Optional[dict], Optional[str]]:
    """Get YouTube video information and return (info_dict, error_message)."""
    try:
        # First try to get title from web (most reliable)
        web_title = get_youtube_title_from_web(url)
        
        # Try yt-dlp for duration and other metadata
        possible_commands = [
            ["yt-dlp", "--dump-json", url],
            ["python", "-m", "yt_dlp", "--dump-json", url],
            [sys.executable, "-m", "yt_dlp", "--dump-json", url]
        ]
        
        for cmd in possible_commands:
            try:
                proc_info = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
                video_info = json.loads(proc_info.stdout)
                
                # Use web title if available, otherwise use yt-dlp title
                if web_title:
                    video_info['title'] = web_title
                    
                return video_info, None
                
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                continue
        
        # If yt-dlp failed but we have web title, create minimal info dict
        if web_title:
            return {
                'title': web_title,
                'duration': 300,  # Default duration, will be checked after download
                'uploader': 'YouTube'
            }, None
        
        # If all methods failed
        return None, "YouTube 정보를 가져올 수 없습니다."
        
    except Exception as e:
        return None, f"YouTube URL 처리 중 오류: {e}"


def download_youtube_audio(url: str, output_path: str) -> Optional[str]:
    """Download audio from YouTube URL and return error message if failed."""
    try:
        possible_commands = [
            ["yt-dlp", "-x", "--audio-format", "mp3", "-o", output_path, url],
            ["python", "-m", "yt_dlp", "-x", "--audio-format", "mp3", "-o", output_path, url],
            [sys.executable, "-m", "yt_dlp", "-x", "--audio-format", "mp3", "-o", output_path, url]
        ]
        
        last_error = None
        
        for cmd in possible_commands:
            try:
                subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=120)
                return None
                
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
                last_error = str(e)
                continue
        
        return f"YouTube 오디오 다운로드 실패: {last_error}"
        
    except Exception as e:
        return f"YouTube 다운로드 중 예상치 못한 오류: {e}"


def separate_audio_with_spleeter(input_path: str, output_dir: str, model: str = "spleeter:2stems") -> Optional[str]:
    """Separate audio using Spleeter and return error message if failed."""
    try:
        # Use `sys.executable` to ensure we're using the python from the current venv
        cmd = [
            sys.executable, "-m", "spleeter", "separate", 
            "-o", output_dir, 
            "-p", model, input_path
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return None
    except FileNotFoundError:
        return "spleeter 실행 파일을 찾을 수 없습니다. 가상 환경에 spleeter가 올바르게 설치되었는지 확인하세요."
    except subprocess.CalledProcessError as e:
        return f"오디오 분리 중 오류: {e.stderr.strip() if e.stderr else e}"


def convert_wav_to_mp3(wav_path: str, mp3_path: str) -> Optional[str]:
    """Convert WAV file to MP3 and return error message if failed."""
    try:
        subprocess.run(["ffmpeg", "-i", wav_path, mp3_path], check=True)
        return None
    except FileNotFoundError:
        return "ffmpeg 실행 파일을 찾을 수 없습니다. ffmpeg가 시스템에 설치되어 있고 PATH에 추가되었는지 확인하세요."
    except subprocess.CalledProcessError as e:
        return f"WAV to MP3 변환 실패: {e.stderr.strip() if e.stderr else e}"


def cleanup_file(filepath: str) -> None:
    """Safely remove a file if it exists."""
    try:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
    except OSError as e:
        print(f"Failed to remove file {filepath}: {e}")


def cleanup_files(*filepaths: str) -> None:
    """Safely remove multiple files."""
    for filepath in filepaths:
        cleanup_file(filepath)