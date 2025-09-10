"""
Main application for the voice-to-text system.
"""

import sys
import threading
import time
import signal
import os
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.logger import logger
from src.utils.config_manager import config
from src.utils.audio_utils import audio_manager
from src.speech_processor import speech_processor
from src.text_insertion import text_inserter
from src.hotkey_handler import hotkey_handler


class VoiceToTextSystem:
    """Main voice-to-text system application."""
    
    def __init__(self):
        self.running = False
        self.processing = False
        self.gui_components = {}
        
        # Flags for recording control
        self._stop_requested = False
        
        # PID file management
        self._pid_dir = project_root / "tmp"
        try:
            self._pid_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create PID directory: {e}")
        self._pid_file = self._pid_dir / "voice-to-text.pid"
        
        # Initialize components
        self._init_components()
        
        logger.info("VoiceToTextSystem initialized")
    
    def _init_components(self):
        """Initialize all system components."""
        try:
            # Set up hotkey callback
            hotkey_handler.set_callback(self._on_hotkey_pressed)
            
            # Load Whisper model
            if not speech_processor.load_model():
                logger.warning("Failed to load Whisper model, will load on first use")
            
            logger.info("All components initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize components: {e}")
            raise
    
    def start(self) -> bool:
        """Start the voice-to-text system."""
        if self.running:
            logger.warning("System already running")
            return True
        
        try:
            # Start hotkey handler
            if not hotkey_handler.start():
                logger.error("Failed to start hotkey handler")
                return False
            
            # Register signal handlers
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
            try:
                # Handle USR1 as a hotkey trigger from xbindkeys script
                signal.signal(signal.SIGUSR1, self._hotkey_signal_handler)
            except Exception as e:
                logger.error(f"Failed to register SIGUSR1 handler: {e}")
            
            # Write PID file so the hotkey script can signal us
            self._write_pid_file()
            
            self.running = True
            logger.info("Voice-to-text system started successfully")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start system: {e}")
            return False
    
    def stop(self):
        """Stop the voice-to-text system."""
        if not self.running:
            return
        
        try:
            self.running = False
            
            # Stop recording if active
            if audio_manager.is_recording():
                audio_manager.stop_recording()
            
            # Stop hotkey handler
            hotkey_handler.stop()
            
            # Clean up temporary files
            audio_manager.cleanup_temp_files()
            
            # Remove PID file
            self._remove_pid_file()
            
            logger.info("Voice-to-text system stopped")
            
        except Exception as e:
            logger.error(f"Error stopping system: {e}")
    
    def _on_hotkey_pressed(self):
        """Handle hotkey press event (toggle start/stop)."""
        try:
            # If we're already recording, treat this as a stop request
            if audio_manager.is_recording():
                logger.info("Hotkey pressed while recording: requesting stop")
                self._stop_requested = True
                return
            
            # If we're already processing (e.g., transcribing), ignore
            if self.processing:
                logger.info("Already processing, ignoring hotkey press during processing phase")
                return
            
            self.processing = True
            self._stop_requested = False
            
            # Start recording
            if not audio_manager.start_recording():
                logger.error("Failed to start recording")
                self.processing = False
                return
            
            # Show recording indicator
            self._show_recording_indicator()
            
            # Wait for user to stop recording (press hotkey again)
            self._wait_for_stop_recording()
            
            # Stop recording
            audio_file = audio_manager.stop_recording()
            if not audio_file:
                logger.error("Failed to get recorded audio")
                self.processing = False
                self._hide_recording_indicator()
                return
            
            # Hide recording indicator
            self._hide_recording_indicator()
            
            # Process audio
            self._process_audio(audio_file)
            
        except Exception as e:
            logger.error(f"Error in hotkey handler: {e}")
        finally:
            self.processing = False
    
    def _wait_for_stop_recording(self):
        """Wait for user to press hotkey again to stop recording or timeout."""
        recording_start = time.time()
        max_duration = 30  # Maximum recording duration in seconds
        
        while audio_manager.is_recording():
            time.sleep(0.1)
            
            # Stop requested via hotkey
            if self._stop_requested:
                logger.info("Stop requested via hotkey")
                break
            
            # Timeout
            if time.time() - recording_start > max_duration:
                logger.info("Recording timeout reached")
                break
    
    def _process_audio(self, audio_file: str):
        """Process recorded audio and insert text."""
        try:
            logger.info("Processing recorded audio...")
            
            # Show processing indicator
            self._show_processing_indicator()
            
            # Transcribe audio
            transcription = speech_processor.transcribe_audio(audio_file)
            
            if transcription:
                # Insert text
                success = text_inserter.insert_text(transcription)
                
                if success:
                    logger.info(f"Text inserted successfully: '{transcription[:50]}...'")
                    self._show_success_indicator()
                else:
                    logger.error("Failed to insert text")
                    self._show_error_indicator("Text insertion failed")
            else:
                logger.warning("No transcription generated")
                self._show_error_indicator("No speech detected")
            
            # Hide processing indicator
            self._hide_processing_indicator()
            
        except Exception as e:
            logger.error(f"Error processing audio: {e}")
            self._show_error_indicator("Processing failed")
            self._hide_processing_indicator()
    
    def _show_recording_indicator(self):
        """Show recording indicator."""
        try:
            # This would show a visual indicator that recording is active
            # For now, just log the event
            logger.info("Recording indicator shown")
        except Exception as e:
            logger.error(f"Failed to show recording indicator: {e}")
    
    def _hide_recording_indicator(self):
        """Hide recording indicator."""
        try:
            logger.info("Recording indicator hidden")
        except Exception as e:
            logger.error(f"Failed to hide recording indicator: {e}")
    
    def _show_processing_indicator(self):
        """Show processing indicator."""
        try:
            logger.info("Processing indicator shown")
        except Exception as e:
            logger.error(f"Failed to show processing indicator: {e}")
    
    def _hide_processing_indicator(self):
        """Hide processing indicator."""
        try:
            logger.info("Processing indicator hidden")
        except Exception as e:
            logger.error(f"Failed to hide processing indicator: {e}")
    
    def _show_success_indicator(self):
        """Show success indicator."""
        try:
            logger.info("Success indicator shown")
        except Exception as e:
            logger.error(f"Failed to show success indicator: {e}")
    
    def _show_error_indicator(self, message: str):
        """Show error indicator."""
        try:
            logger.error(f"Error indicator shown: {message}")
        except Exception as e:
            logger.error(f"Failed to show error indicator: {e}")
    
    def _signal_handler(self, signum, frame):
        """Handle system signals for graceful shutdown."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)

    def _hotkey_signal_handler(self, signum, frame):
        """Handle SIGUSR1 as a hotkey trigger from xbindkeys script."""
        try:
            logger.info("Received SIGUSR1 hotkey signal")
            # Directly toggle behavior: if recording, request stop; else start
            if audio_manager.is_recording():
                self._stop_requested = True
            else:
                # Spawn a thread to run the standard hotkey flow
                threading.Thread(target=self._on_hotkey_pressed, daemon=True).start()
        except Exception as e:
            logger.error(f"Error handling SIGUSR1: {e}")
    
    def get_status(self) -> dict:
        """Get system status."""
        return {
            'running': self.running,
            'processing': self.processing,
            'recording': audio_manager.is_recording(),
            'hotkey': hotkey_handler.get_status(),
            'audio_devices': len(audio_manager.get_audio_devices()),
            'whisper_model': speech_processor.get_model_info()
        }

    def _write_pid_file(self):
        """Write the current process ID to the PID file."""
        try:
            pid = os.getpid()
            with open(self._pid_file, 'w') as f:
                f.write(str(pid))
            logger.debug(f"PID file written: {self._pid_file} (pid={pid})")
        except Exception as e:
            logger.error(f"Failed to write PID file: {e}")

    def _remove_pid_file(self):
        """Remove the PID file if it exists."""
        try:
            if self._pid_file.exists():
                self._pid_file.unlink()
                logger.debug("PID file removed")
        except Exception as e:
            logger.error(f"Failed to remove PID file: {e}")
    
    def run(self):
        """Run the main application loop."""
        try:
            if not self.start():
                logger.error("Failed to start voice-to-text system")
                return False
            
            logger.info("Voice-to-text system running. Press Ctrl+C to stop.")
            
            # Main loop
            while self.running:
                time.sleep(1)
            
            return True
            
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
            self.stop()
            return True
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            self.stop()
            return False


def main():
    """Main entry point."""
    try:
        # Create and run the system
        system = VoiceToTextSystem()
        success = system.run()
        
        if success:
            logger.info("Voice-to-text system exited successfully")
            return 0
        else:
            logger.error("Voice-to-text system exited with errors")
            return 1
            
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
