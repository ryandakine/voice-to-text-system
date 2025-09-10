"""
Speech processing module using Whisper for speech-to-text conversion.
"""

import whisper
import os
import tempfile
import time
from typing import Optional, Dict, Any
from pathlib import Path

from .utils.logger import logger
from .utils.config_manager import config


class SpeechProcessor:
    """Handles speech-to-text conversion using Whisper."""
    
    def __init__(self):
        self.model = None
        self.model_name = config.get('Whisper', 'model', 'base')
        self.language = config.get('Whisper', 'language', 'auto')
        self.task = config.get('Whisper', 'task', 'transcribe')
        self.temperature = config.getfloat('Whisper', 'temperature', 0.0)
        
        # Model cache directory
        self.cache_dir = Path.home() / ".cache" / "whisper"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"SpeechProcessor initialized with model: {self.model_name}")
    
    def load_model(self, model_name: Optional[str] = None) -> bool:
        """Load Whisper model."""
        if model_name:
            self.model_name = model_name
        
        try:
            logger.info(f"Loading Whisper model: {self.model_name}")
            
            # Load model with caching
            self.model = whisper.load_model(
                self.model_name,
                download_root=str(self.cache_dir)
            )
            
            logger.info(f"Whisper model {self.model_name} loaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load Whisper model {self.model_name}: {e}")
            return False
    
    def transcribe_audio(self, audio_file: str) -> Optional[str]:
        """Transcribe audio file to text using Whisper."""
        if not self.model:
            if not self.load_model():
                logger.error("No Whisper model available for transcription")
                return None
        
        if not os.path.exists(audio_file):
            logger.error(f"Audio file not found: {audio_file}")
            return None
        
        try:
            logger.info(f"Starting transcription of: {audio_file}")
            start_time = time.time()
            
            # Transcribe with Whisper
            result = self.model.transcribe(
                audio_file,
                language=self.language if self.language != 'auto' else None,
                task=self.task,
                temperature=self.temperature,
                fp16=False  # Use CPU for compatibility
            )
            
            transcription = result.get('text', '').strip()
            processing_time = time.time() - start_time
            
            logger.log_audio_event(
                "TRANSCRIPTION_COMPLETED",
                f"duration={processing_time:.2f}s, length={len(transcription)}"
            )
            
            if transcription:
                logger.info(f"Transcription successful: '{transcription[:50]}...'")
                return transcription
            else:
                logger.warning("Transcription returned empty text")
                return None
                
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return None
    
    def transcribe_with_options(self, audio_file: str, options: Dict[str, Any]) -> Optional[str]:
        """Transcribe audio with custom options."""
        if not self.model:
            if not self.load_model():
                return None
        
        try:
            # Merge options with defaults
            transcribe_options = {
                'language': self.language if self.language != 'auto' else None,
                'task': self.task,
                'temperature': self.temperature,
                'fp16': False
            }
            transcribe_options.update(options)
            
            logger.info(f"Transcribing with custom options: {transcribe_options}")
            
            result = self.model.transcribe(audio_file, **transcribe_options)
            transcription = result.get('text', '').strip()
            
            return transcription if transcription else None
            
        except Exception as e:
            logger.error(f"Custom transcription failed: {e}")
            return None
    
    def get_available_models(self) -> list:
        """Get list of available Whisper models."""
        return ['tiny', 'base', 'small', 'medium', 'large']
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model."""
        if not self.model:
            return {'loaded': False, 'name': self.model_name}
        
        return {
            'loaded': True,
            'name': self.model_name,
            'language': self.language,
            'task': self.task,
            'temperature': self.temperature
        }
    
    def update_model(self, model_name: str) -> bool:
        """Update to a different Whisper model."""
        if model_name not in self.get_available_models():
            logger.error(f"Invalid model name: {model_name}")
            return False
        
        try:
            # Unload current model
            self.model = None
            
            # Update configuration
            config.update_whisper_model(model_name)
            self.model_name = model_name
            
            # Load new model
            return self.load_model()
            
        except Exception as e:
            logger.error(f"Failed to update model: {e}")
            return False
    
    def update_language(self, language: str):
        """Update the language setting."""
        self.language = language
        config.set('Whisper', 'language', language)
        config.save_config()
        logger.info(f"Language updated to: {language}")
    
    def update_task(self, task: str):
        """Update the task setting (transcribe/translate)."""
        if task not in ['transcribe', 'translate']:
            logger.error(f"Invalid task: {task}")
            return
        
        self.task = task
        config.set('Whisper', 'task', task)
        config.save_config()
        logger.info(f"Task updated to: {task}")
    
    def cleanup_cache(self):
        """Clean up Whisper model cache."""
        try:
            # Remove old model files
            for model_file in self.cache_dir.glob("*.pt"):
                model_file.unlink()
            logger.info("Whisper cache cleaned up")
        except Exception as e:
            logger.error(f"Failed to cleanup cache: {e}")
    
    def get_model_size(self, model_name: str) -> Optional[str]:
        """Get the size of a Whisper model."""
        model_sizes = {
            'tiny': '39 MB',
            'base': '74 MB',
            'small': '244 MB',
            'medium': '769 MB',
            'large': '1550 MB'
        }
        return model_sizes.get(model_name)
    
    def estimate_processing_time(self, audio_duration: float) -> float:
        """Estimate processing time for audio of given duration."""
        # Rough estimates based on model size and audio duration
        model_factors = {
            'tiny': 0.5,
            'base': 1.0,
            'small': 2.0,
            'medium': 4.0,
            'large': 8.0
        }
        
        factor = model_factors.get(self.model_name, 1.0)
        return audio_duration * factor


# Global speech processor instance
speech_processor = SpeechProcessor()
