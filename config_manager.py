import os
import configparser
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class ConfigManager:
    """Configuration management for the vocal separation application."""
    
    def __init__(self, config_file: str = 'config.ini'):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from file with fallback to defaults."""
        if not os.path.exists(self.config_file):
            print(f"Warning: {self.config_file} not found, using default values")
            self._use_defaults()
            return
        
        try:
            self.config.read(self.config_file)
            print(f"Configuration loaded from {self.config_file}")
        except Exception as e:
            print(f"Error reading {self.config_file}: {e}")
            self._use_defaults()
    
    def _use_defaults(self) -> None:
        """Set default configuration values."""
        self.config.add_section('LIMITS')
        self.config.set('LIMITS', 'MAX_FILE_SIZE_MB', '50')
        self.config.set('LIMITS', 'MAX_DURATION_SECONDS', '600')
    
    def get_max_file_size_mb(self) -> int:
        """Get maximum file size in MB."""
        # Check environment variable first, then config file, then default
        env_value = os.getenv('MAX_FILE_SIZE_MB')
        if env_value:
            try:
                return int(env_value)
            except ValueError:
                pass
        
        try:
            return self.config.getint('LIMITS', 'MAX_FILE_SIZE_MB')
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return 50
    
    def get_max_duration_seconds(self) -> int:
        """Get maximum duration in seconds."""
        # Check environment variable first, then config file, then default
        env_value = os.getenv('MAX_DURATION_SECONDS')
        if env_value:
            try:
                return int(env_value)
            except ValueError:
                pass
        
        try:
            return self.config.getint('LIMITS', 'MAX_DURATION_SECONDS')
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return 600
    
    def get_upload_dir(self) -> str:
        """Get upload directory path."""
        return os.getenv('UPLOAD_DIR', 'uploads')
    
    def get_output_dir(self) -> str:
        """Get output directory path."""
        return os.getenv('OUTPUT_DIR', 'outputs')
    
    def get_spleeter_model(self) -> str:
        """Get spleeter model configuration."""
        return os.getenv('SPLEETER_MODEL', 'spleeter:2stems')
    
    def get_max_concurrent_tasks(self) -> int:
        """Get maximum concurrent tasks."""
        env_value = os.getenv('MAX_CONCURRENT_TASKS')
        if env_value:
            try:
                return int(env_value)
            except ValueError:
                pass
        
        try:
            return self.config.getint('CONCURRENCY', 'MAX_CONCURRENT_TASKS')
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return 3
    
    def get_task_timeout_seconds(self) -> int:
        """Get task timeout in seconds."""
        env_value = os.getenv('TASK_TIMEOUT_SECONDS')
        if env_value:
            try:
                return int(env_value)
            except ValueError:
                pass
        
        try:
            return self.config.getint('CONCURRENCY', 'TASK_TIMEOUT_SECONDS')
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return 600


# Global config instance
config_manager = ConfigManager()