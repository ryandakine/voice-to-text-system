import threading
import time
import signal
import sys
from typing import Optional, Any
from .interfaces import TranscriptionService, OutputService
from .input_strategy import InputStrategy, HotkeyInputStrategy, PTTInputStrategy
from .utils.audio_utils import AudioManager
from .utils.logger import logger
from .utils.config_manager import config

class VoiceToTextApp:
    """
    Unified Voice-to-Text Application.
    Orchestrates Audio Recording, Transcription, and Text Insertion.
    """
    def __init__(self, 
                 transcription_service: TranscriptionService,
                 output_service: OutputService,
                 input_strategy: InputStrategy,
                 audio_manager: Optional[AudioManager] = None):
        
        self.transcription_service = transcription_service
        self.output_service = output_service
        self.input_strategy = input_strategy
        self.audio_manager = audio_manager or AudioManager()
        
        self.running = False
        self.processing = False
        
        # Determine audio device from config
        self.audio_device_index = config.getint('Audio', 'device_index', -1)
        self.sample_rate = config.getint('Audio', 'sample_rate', 16000)

    def start(self):
        """Start the application loop."""
        if self.running:
            return
            
        self.running = True
        logger.info("VoiceToTextApp starting...")
        
        # Initialize input strategy
        success = self.input_strategy.start(
            on_start_recording=self.start_recording,
            on_stop_recording=self.stop_recording
        )
        
        if not success:
            logger.error("Failed to start input strategy. Exiting.")
            self.running = False
            return

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info("System Ready. Waiting for input...")
        
        # Keep main thread alive
        try:
            while self.running:
                time.sleep(0.1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        """Stop the application."""
        self.running = False
        self.input_strategy.stop()
        self.audio_manager.cleanup_temp_files()
        logger.info("VoiceToTextApp stopped.")

    def start_recording(self):
        """Handle start recording event."""
        if self.processing:
            logger.warning("Still processing previous audio. Ignoring start request.")
            return

        logger.info("Starting recording...")
        self.audio_manager.start_recording(
            device_index=self.audio_device_index,
            sample_rate=self.sample_rate
        )

    def stop_recording(self):
        """Handle stop recording event."""
        logger.info("Stopping recording...")
        audio_file = self.audio_manager.stop_recording()
        
        if audio_file:
            # Process in background thread to not block input
            processing_thread = threading.Thread(
                target=self._process_audio,
                args=(audio_file,),
                daemon=True
            )
            processing_thread.start()
        else:
            logger.warning("No audio file captured.")

    def _process_audio(self, audio_file: str):
        """Transcribe and insert text."""
        self.processing = True
        try:
            logger.info(f"Transcribing {audio_file}...")
            text = self.transcription_service.transcribe_audio(audio_file)
            
            if text:
                logger.info(f"Transcribed: '{text}'")
                success = self.output_service.insert_text(text)
                if success:
                    logger.info("Text inserted successfully.")
                else:
                    logger.error("Failed to insert text.")
            else:
                logger.info("No speech detected.")
                
        except Exception as e:
            logger.error(f"Error processing audio: {e}")
        finally:
            self.processing = False
            # Clean up the specific file if needed, or let manager handle it on exit
            # For now, manager handles temp dir cleanup on exit/init

    def _signal_handler(self, signum, frame):
        logger.info("Signal received. Shutting down...")
        self.stop()
        sys.exit(0)
