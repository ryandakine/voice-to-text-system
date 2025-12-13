"""
Configuration management for the voice-to-text system.
"""

import configparser
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from .logger import logger


class ConfigManager:
    """Manages configuration for the voice-to-text system."""
    
    def __init__(self):
        self.config_dir = Path.home() / ".config" / "voice-to-text"
        self.config_file = self.config_dir / "config.ini"
        self.config = configparser.ConfigParser()
        
        # Create config directory if it doesn't exist
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Load or create default configuration
        self._load_config()
    
    def _load_config(self):
        """Load configuration from file or create default."""
        if self.config_file.exists():
            try:
                self.config.read(self.config_file)
                logger.info("Configuration loaded from file")
            except Exception as e:
                logger.error(f"Failed to load configuration: {e}")
                self._create_default_config()
        else:
            self._create_default_config()
    
    def _create_default_config(self):
        """Create default configuration."""
        self.config['General'] = {
            'hotkey': 'F5',
            'auto_start': 'true',
            'show_system_tray': 'true',
            'log_level': 'INFO'
        }
        
        self.config['Audio'] = {
            'sample_rate': '16000',
            'channels': '1',
            'chunk_size': '1024',
            'format': 'pyaudio.paInt16',
            'device_index': '-1'  # -1 means default device
        }
        
        self.config['Whisper'] = {
            'model': 'base',
            'language': 'auto',
            'task': 'transcribe',
            'temperature': '0.0',
            'device': 'cpu',
            'fp16': 'false'
        }
        
        self.config['TextInsertion'] = {
            'primary_method': 'clipboard',
            'fallback_method': 'keyboard',
            'delay_before_insert': '0.1',
            'clear_clipboard_after': 'true',
            'supported_apps': 'firefox,chrome,chromium,brave,code,code-oss,sublime_text,gedit,mousepad,leafpad,libreoffice,libreoffice-writer,terminal,gnome-terminal,xfce4-terminal,konsole,tilix,terminator'
        }
        
        self.config['GUI'] = {
            'status_window_timeout': '3.0',
            'show_recording_indicator': 'true',
            'recording_indicator_color': '#ff4444'
        }
        
        self.save_config()
        logger.info("Default configuration created")
    
    def save_config(self):
        """Save configuration to file."""
        try:
            with open(self.config_file, 'w') as f:
                self.config.write(f)
            logger.debug("Configuration saved")
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
    
    def get(self, section: str, key: str, fallback: Any = None) -> Any:
        """Get configuration value."""
        try:
            return self.config.get(section, key, fallback=fallback)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return fallback
    
    def getint(self, section: str, key: str, fallback: int = 0) -> int:
        """Get integer configuration value."""
        try:
            return self.config.getint(section, key, fallback=fallback)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return fallback
    
    def getfloat(self, section: str, key: str, fallback: float = 0.0) -> float:
        """Get float configuration value."""
        try:
            return self.config.getfloat(section, key, fallback=fallback)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return fallback
    
    def getboolean(self, section: str, key: str, fallback: bool = False) -> bool:
        """Get boolean configuration value."""
        try:
            return self.config.getboolean(section, key, fallback=fallback)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return fallback
    
    def set(self, section: str, key: str, value: Any):
        """Set configuration value."""
        if not self.config.has_section(section):
            self.config.add_section(section)
        
        self.config.set(section, key, str(value))
        logger.debug(f"Configuration updated: {section}.{key} = {value}")
    
    def get_audio_config(self) -> Dict[str, Any]:
        """Get audio configuration as dictionary."""
        return {
            'sample_rate': self.getint('Audio', 'sample_rate', 16000),
            'channels': self.getint('Audio', 'channels', 1),
            'chunk_size': self.getint('Audio', 'chunk_size', 1024),
            'format': self.get('Audio', 'format', 'pyaudio.paInt16'),
            'device_index': self.getint('Audio', 'device_index', -1)
        }
    
    def get_whisper_config(self) -> Dict[str, Any]:
        """Get Whisper configuration as dictionary."""
        return {
            'model': self.get('Whisper', 'model', 'base'),
            'language': self.get('Whisper', 'language', 'auto'),
            'task': self.get('Whisper', 'task', 'transcribe'),
            'temperature': self.getfloat('Whisper', 'temperature', 0.0),
            'device': self.get('Whisper', 'device', 'cpu'),
            'fp16': self.getboolean('Whisper', 'fp16', False)
        }
    
    def get_text_insertion_config(self) -> Dict[str, Any]:
        """Get text insertion configuration as dictionary."""
        return {
            'primary_method': self.get('TextInsertion', 'primary_method', 'clipboard'),
            'fallback_method': self.get('TextInsertion', 'fallback_method', 'keyboard'),
            'delay_before_insert': self.getfloat('TextInsertion', 'delay_before_insert', 0.1),
            'clear_clipboard_after': self.getboolean('TextInsertion', 'clear_clipboard_after', True),
            'supported_apps': self.get('TextInsertion', 'supported_apps', '').split(',')
        }
    
    def get_gui_config(self) -> Dict[str, Any]:
        """Get GUI configuration as dictionary."""
        return {
            'status_window_timeout': self.getfloat('GUI', 'status_window_timeout', 3.0),
            'show_recording_indicator': self.getboolean('GUI', 'show_recording_indicator', True),
            'recording_indicator_color': self.get('GUI', 'recording_indicator_color', '#ff4444')
        }
    
    def update_audio_device(self, device_index: int):
        """Update the selected audio device."""
        self.set('Audio', 'device_index', device_index)
        self.save_config()
        logger.info(f"Audio device updated to index: {device_index}")
    
    def update_hotkey(self, hotkey: str):
        """Update the global hotkey."""
        self.set('General', 'hotkey', hotkey)
        self.save_config()
        logger.info(f"Hotkey updated to: {hotkey}")
    
    def update_whisper_model(self, model: str):
        """Update the Whisper model."""
        self.set('Whisper', 'model', model)
        self.save_config()
        logger.info(f"Whisper model updated to: {model}")


# Global configuration instance
config = ConfigManager()
