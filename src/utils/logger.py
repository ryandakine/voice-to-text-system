"""
Logging utilities for the voice-to-text system.
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path


class Logger:
    """Centralized logging for the voice-to-text system."""
    
    def __init__(self, name="voice-to-text", log_level=logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(log_level)
        
        # Prevent duplicate handlers
        if not self.logger.handlers:
            self._setup_handlers()
    
    def _setup_handlers(self):
        """Set up logging handlers for file and console output."""
        # Create logs directory
        log_dir = Path.home() / ".local" / "share" / "voice-to-text" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # File handler
        log_file = log_dir / f"voice-to-text-{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # Add handlers
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def debug(self, message):
        """Log debug message."""
        self.logger.debug(message)
    
    def info(self, message):
        """Log info message."""
        self.logger.info(message)
    
    def warning(self, message):
        """Log warning message."""
        self.logger.warning(message)
    
    def error(self, message):
        """Log error message."""
        self.logger.error(message)
    
    def critical(self, message):
        """Log critical message."""
        self.logger.critical(message)
    
    def log_audio_event(self, event_type, details=None):
        """Log audio-related events."""
        message = f"AUDIO_EVENT: {event_type}"
        if details:
            message += f" - {details}"
        self.info(message)
    
    def log_hotkey_event(self, key, action):
        """Log hotkey events."""
        self.info(f"HOTKEY: {key} - {action}")
    
    def log_text_insertion(self, method, success, details=None):
        """Log text insertion events."""
        status = "SUCCESS" if success else "FAILED"
        message = f"TEXT_INSERTION: {method} - {status}"
        if details:
            message += f" - {details}"
        self.info(message)


# Global logger instance
logger = Logger()
