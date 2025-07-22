import asyncio
import time
import uuid
from enum import Enum
from typing import Dict, Optional, Any
from dataclasses import dataclass, asdict
import threading
from concurrent.futures import ThreadPoolExecutor

from config_manager import config_manager
from file_handlers import validate_file_upload, validate_youtube_url, process_audio_separation
from logger import app_logger


class TaskStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class Task:
    task_id: str
    status: TaskStatus
    progress: int
    message: str
    created_at: float
    updated_at: float
    input_path: Optional[str] = None
    basename: Optional[str] = None
    vocal_url: Optional[str] = None
    inst_url: Optional[str] = None
    original_url: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['status'] = self.status.value
        return data


class TaskManager:
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.max_concurrent_tasks = config_manager.get_max_concurrent_tasks()
        self.task_timeout = config_manager.get_task_timeout_seconds()
        self.executor = ThreadPoolExecutor(max_workers=self.max_concurrent_tasks)
        self.active_tasks = 0
        self.lock = threading.Lock()
        
        app_logger.info(f"TaskManager initialized - max_workers: {self.max_concurrent_tasks}, timeout: {self.task_timeout}s")

    def create_task_immediate(self) -> str:
        """Create a new background task immediately without input validation."""
        task_id = str(uuid.uuid4())
        
        task = Task(
            task_id=task_id,
            status=TaskStatus.PENDING,
            progress=0,
            message="작업이 대기열에 추가되었습니다.",
            created_at=time.time(),
            updated_at=time.time()
        )
        
        self.tasks[task_id] = task
        app_logger.info(f"Created immediate task {task_id}")
        
        return task_id
    
    def create_task(self, input_path: str, basename: str) -> str:
        """Create a new background task (legacy method for compatibility)."""
        task_id = str(uuid.uuid4())
        
        task = Task(
            task_id=task_id,
            status=TaskStatus.PENDING,
            progress=0,
            message="작업이 대기열에 추가되었습니다.",
            created_at=time.time(),
            updated_at=time.time(),
            input_path=input_path,
            basename=basename
        )
        
        self.tasks[task_id] = task
        app_logger.info(f"Created task {task_id} for file: {basename}")
        
        return task_id

    def submit_task(self, task_id: str) -> bool:
        """Submit task to thread pool if capacity allows."""
        with self.lock:
            if self.active_tasks >= self.max_concurrent_tasks:
                app_logger.warning(f"Task queue full, rejecting task {task_id}")
                self.tasks[task_id].status = TaskStatus.FAILED
                self.tasks[task_id].message = "서버가 바쁩니다. 잠시 후 다시 시도해주세요."
                self.tasks[task_id].error_message = "Task queue full"
                return False
            
            self.active_tasks += 1
            app_logger.info(f"Submitting task {task_id} to thread pool ({self.active_tasks}/{self.max_concurrent_tasks})")
        
        # Submit to thread pool
        future = self.executor.submit(self._process_task, task_id)
        return True
    
    def submit_task_with_input(self, task_id: str, file, youtube_url: str, max_size_mb: int, max_duration: int, upload_dir: str) -> bool:
        """Submit task with input data for processing."""
        with self.lock:
            if self.active_tasks >= self.max_concurrent_tasks:
                app_logger.warning(f"Task queue full, rejecting task {task_id}")
                task = self.tasks.get(task_id)
                if task:
                    task.status = TaskStatus.FAILED
                    task.message = "서버가 바쁩니다. 잠시 후 다시 시도해주세요."
                    task.error_message = "Task queue full"
                return False
            
            self.active_tasks += 1
            app_logger.info(f"Submitting task with input {task_id} to thread pool ({self.active_tasks}/{self.max_concurrent_tasks})")
        
        # Submit to thread pool with input processing
        future = self.executor.submit(self._process_task_with_input, task_id, file, youtube_url, max_size_mb, max_duration, upload_dir)
        return True

    def _process_task(self, task_id: str):
        """Process audio separation task in background thread."""
        task = self.tasks.get(task_id)
        if not task:
            return
        
        try:
            # Update status to processing
            task.status = TaskStatus.PROCESSING
            task.progress = 10
            task.message = "음성 분리 작업을 시작합니다..."
            task.updated_at = time.time()
            
            app_logger.info(f"Starting audio separation for task {task_id}")
            
            # Simulate progress updates
            self._update_progress(task_id, 20, "파일 분석 중...")
            
            # Get configuration
            spleeter_model = config_manager.get_spleeter_model()
            output_dir = config_manager.get_output_dir()
            
            # Process audio separation
            self._update_progress(task_id, 40, "AI 모델로 음성 분리 중...")
            
            vocal_mp3_path, inst_mp3_path, error = process_audio_separation(
                task.input_path, task.basename, output_dir, spleeter_model
            )
            
            if error:
                task.status = TaskStatus.FAILED
                task.error_message = error
                task.message = f"음성 분리 실패: {error}"
                app_logger.error(f"Task {task_id} failed: {error}")
            else:
                # Success - create download URLs
                from urllib.parse import quote
                encoded_basename = quote(task.basename)
                
                task.status = TaskStatus.COMPLETED
                task.progress = 100
                task.message = "음성 분리가 완료되었습니다!"
                task.vocal_url = f"/download?f={encoded_basename}&t=v"
                task.inst_url = f"/download?f={encoded_basename}&t=a"
                task.original_url = f"/download?f={encoded_basename}&t=o"
                
                app_logger.info(f"Task {task_id} completed successfully")
                
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            task.message = f"예상치 못한 오류: {e}"
            app_logger.error(f"Task {task_id} failed with exception: {e}")
            
        finally:
            task.updated_at = time.time()
            with self.lock:
                self.active_tasks -= 1
                app_logger.info(f"Task {task_id} finished. Active tasks: {self.active_tasks}")

    def _process_task_with_input(self, task_id: str, file, youtube_url: str, max_size_mb: int, max_duration: int, upload_dir: str):
        """Process task with input validation and audio separation in background thread."""
        task = self.tasks.get(task_id)
        if not task:
            return
        
        try:
            # Update status to processing
            task.status = TaskStatus.PROCESSING
            task.progress = 5
            task.message = "입력 데이터 검증 중..."
            task.updated_at = time.time()
            
            app_logger.info(f"Starting input validation for task {task_id}")
            
            # Validate and process input
            if file and file.filename:
                app_logger.info(f"Processing file upload: {file.filename}")
                self._update_progress(task_id, 10, "파일 업로드 검증 중...")
                
                input_path, basename, error = validate_file_upload(
                    file, max_size_mb, max_duration, upload_dir
                )
                if error:
                    task.status = TaskStatus.FAILED
                    task.error_message = error
                    task.message = f"파일 검증 실패: {error}"
                    app_logger.error(f"Task {task_id} file validation failed: {error}")
                    return
                    
            elif youtube_url:
                app_logger.info(f"Processing YouTube URL: {youtube_url}")
                self._update_progress(task_id, 10, "YouTube URL 검증 중...")
                
                input_path, basename, error = validate_youtube_url(
                    youtube_url, max_size_mb, max_duration, upload_dir
                )
                if error:
                    task.status = TaskStatus.FAILED
                    task.error_message = error
                    task.message = f"YouTube 다운로드 실패: {error}"
                    app_logger.error(f"Task {task_id} YouTube validation failed: {error}")
                    return
            else:
                task.status = TaskStatus.FAILED
                task.error_message = "No input provided"
                task.message = "파일 또는 YouTube URL이 제공되지 않았습니다."
                app_logger.error(f"Task {task_id} failed: No input provided")
                return
            
            # Update task with validated input data
            task.input_path = input_path
            task.basename = basename
            
            # Continue with audio separation
            self._update_progress(task_id, 30, "파일 분석 중...")
            
            # Get configuration
            spleeter_model = config_manager.get_spleeter_model()
            output_dir = config_manager.get_output_dir()
            
            # Process audio separation
            self._update_progress(task_id, 50, "AI 모델로 음성 분리 중...")
            
            vocal_mp3_path, inst_mp3_path, error = process_audio_separation(
                input_path, basename, output_dir, spleeter_model
            )
            
            if error:
                task.status = TaskStatus.FAILED
                task.error_message = error
                task.message = f"음성 분리 실패: {error}"
                app_logger.error(f"Task {task_id} audio separation failed: {error}")
            else:
                # Success - create download URLs
                from urllib.parse import quote
                encoded_basename = quote(basename)
                
                task.status = TaskStatus.COMPLETED
                task.progress = 100
                task.message = "음성 분리가 완료되었습니다!"
                task.vocal_url = f"/download?f={encoded_basename}&t=v"
                task.inst_url = f"/download?f={encoded_basename}&t=a"
                task.original_url = f"/download?f={encoded_basename}&t=o"
                
                app_logger.info(f"Task {task_id} completed successfully")
                
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            task.message = f"예상치 못한 오류: {e}"
            app_logger.error(f"Task {task_id} failed with exception: {e}")
            
        finally:
            task.updated_at = time.time()
            with self.lock:
                self.active_tasks -= 1
                app_logger.info(f"Task {task_id} finished. Active tasks: {self.active_tasks}")

    def _update_progress(self, task_id: str, progress: int, message: str):
        """Update task progress."""
        task = self.tasks.get(task_id)
        if task:
            task.progress = progress
            task.message = message
            task.updated_at = time.time()

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID."""
        return self.tasks.get(task_id)

    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """Clean up old completed/failed tasks."""
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        tasks_to_remove = []
        for task_id, task in self.tasks.items():
            if (current_time - task.updated_at) > max_age_seconds:
                if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.TIMEOUT]:
                    tasks_to_remove.append(task_id)
        
        for task_id in tasks_to_remove:
            del self.tasks[task_id]
            app_logger.info(f"Cleaned up old task: {task_id}")

    def get_stats(self) -> Dict[str, Any]:
        """Get task manager statistics."""
        total_tasks = len(self.tasks)
        pending_tasks = sum(1 for t in self.tasks.values() if t.status == TaskStatus.PENDING)
        processing_tasks = sum(1 for t in self.tasks.values() if t.status == TaskStatus.PROCESSING)
        completed_tasks = sum(1 for t in self.tasks.values() if t.status == TaskStatus.COMPLETED)
        failed_tasks = sum(1 for t in self.tasks.values() if t.status == TaskStatus.FAILED)
        
        return {
            "total_tasks": total_tasks,
            "pending_tasks": pending_tasks,
            "processing_tasks": processing_tasks,
            "completed_tasks": completed_tasks,
            "failed_tasks": failed_tasks,
            "active_workers": self.active_tasks,
            "max_workers": self.max_concurrent_tasks
        }


# Global task manager instance
task_manager = TaskManager()