"""
Main application for the voice-to-text system with push-to-talk support.
Uses Alt key for push-to-talk: hold to record, release to transcribe.
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
from src.push_to_talk_handler import push_to_talk_handler


class VoiceToTextSystemPTT:
    """Voice-to-text system with push-to-talk functionality."""
    
    def __init__(self):
        self.running = False
        self.processing = False
        self.gui_components = {}
        
        # Initialize components
        self._init_components()
        
        logger.info("VoiceToTextSystemPTT initialized with push-to-talk support")
    
    def _init_components(self):
        """Initialize all system components."""
        try:
            # Set up push-to-talk callbacks
            push_to_talk_handler.set_callbacks(
                on_start=self._on_recording_start,
                on_stop=self._on_recording_stop
            )
            
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
            # Start push-to-talk handler
            if not push_to_talk_handler.start():
                logger.error("Failed to start push-to-talk handler")
                return False
            
            # Register signal handlers
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
            
            self.running = True
            logger.info("Voice-to-text system started successfully")
            logger.info("Hold Alt key to record, release to transcribe")
            print("\n" + "="*60)
            print("Voice-to-Text System with Push-to-Talk is running!")
            print("Hold Alt key to record, release to transcribe")
            print("Press Ctrl+C to exit")
            print("="*60 + "\n")
            
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
            
            # Stop push-to-talk handler
            push_to_talk_handler.stop()
            
            # Clean up temporary files
            audio_manager.cleanup_temp_files()
            
            logger.info("Voice-to-text system stopped")
            print("\nVoice-to-Text System stopped.")
            
        except Exception as e:
            logger.error(f"Error stopping system: {e}")
    
    def _on_recording_start(self):
        """Handle recording start event (Alt key pressed)."""
        try:
            # Check if already processing
            if self.processing:
                logger.info("Already processing, ignoring recording start request")
                return
            
            # Start recording
            if not audio_manager.start_recording():
                logger.error("Failed to start recording")
                return
            
            # Show recording indicator
            self._show_recording_indicator()
            logger.info("Recording started - speak now...")
            
        except Exception as e:
            logger.error(f"Error starting recording: {e}")
    
    def _on_recording_stop(self):
        """Handle recording stop event (Alt key released)."""
        try:
            # Stop recording
            audio_file = audio_manager.stop_recording()
            
            # Hide recording indicator
            self._hide_recording_indicator()
            
            if not audio_file:
                logger.error("Failed to get recorded audio")
                return
            
            # Process audio in a separate thread to avoid blocking
            threading.Thread(
                target=self._process_audio,
                args=(audio_file,),
                daemon=True
            ).start()
            
        except Exception as e:
            logger.error(f"Error stopping recording: {e}")
    
    def _process_audio(self, audio_file: str):
        """Process recorded audio and insert text."""
        try:
            self.processing = True
            logger.info("Processing recorded audio...")
            
            # Show processing indicator
            self._show_processing_indicator()
            
            # Transcribe audio
            transcription = speech_processor.transcribe_audio(audio_file)
            
            if transcription:
                logger.info(f"Transcription: {transcription}")
                
                # Insert text at cursor position
                success = text_inserter.insert_text(transcription)
                
                if success:
                    logger.info("Text inserted successfully")
                else:
                    logger.error("Failed to insert text")
                    # Try fallback method
                    text_inserter.insert_text_fallback(transcription)
            else:
                logger.warning("No transcription received")
            
            # Hide processing indicator
            self._hide_processing_indicator()
            
            # Clean up audio file
            try:
                if os.path.exists(audio_file):
                    os.remove(audio_file)
            except Exception as e:
                logger.warning(f"Failed to clean up audio file: {e}")
            
        except Exception as e:
            logger.error(f"Error processing audio: {e}")
        finally:
            self.processing = False
    
    def _show_recording_indicator(self):
        """Show recording indicator to user."""
        try:
            # Print to console for now
            print("🔴 RECORDING... (Release Alt to stop)")
            
            # TODO: Add visual indicator overlay or system tray notification
            if 'tray_icon' in self.gui_components:
                self.gui_components['tray_icon'].set_recording_state(True)
                
        except Exception as e:
            logger.warning(f"Failed to show recording indicator: {e}")
    
    def _hide_recording_indicator(self):
        """Hide recording indicator."""
        try:
            print("⭕ Recording stopped")
            
            # TODO: Hide visual indicator
            if 'tray_icon' in self.gui_components:
                self.gui_components['tray_icon'].set_recording_state(False)
                
        except Exception as e:
            logger.warning(f"Failed to hide recording indicator: {e}")
    
    def _show_processing_indicator(self):
        """Show processing indicator to user."""
        try:
            print("🔄 Processing audio...")
            
            # TODO: Add visual indicator
            if 'tray_icon' in self.gui_components:
                self.gui_components['tray_icon'].set_processing_state(True)
                
        except Exception as e:
            logger.warning(f"Failed to show processing indicator: {e}")
    
    def _hide_processing_indicator(self):
        """Hide processing indicator."""
        try:
            print("✅ Processing complete")
            
            # TODO: Hide visual indicator
            if 'tray_icon' in self.gui_components:
                self.gui_components['tray_icon'].set_processing_state(False)
                
        except Exception as e:
            logger.warning(f"Failed to hide processing indicator: {e}")
    
    def _signal_handler(self, signum, frame):
        """Handle system signals for graceful shutdown."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)
    
    def run(self):
        """Run the main application loop."""
        if not self.start():
            logger.error("Failed to start voice-to-text system")
            return 1
        
        try:
            # Keep the application running
            while self.running:
                time.sleep(0.1)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        finally:
            self.stop()
        
        return 0


def main():
    """Main entry point for the application."""
    try:
        # Create and run the application
        app = VoiceToTextSystemPTT()
        return app.run()
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
