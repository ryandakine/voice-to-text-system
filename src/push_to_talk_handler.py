"""
Push-to-talk handler for voice recording using Alt key.
Hold Alt to record, release to stop and transcribe.
"""

import threading
import time
from typing import Optional, Callable
from pynput import keyboard

from .utils.logger import logger
from .utils.config_manager import config


class PushToTalkHandler:
    """Handles push-to-talk functionality using the Alt key."""
    
    def __init__(self):
        self.listener = None
        self.is_running = False
        self.is_recording = False
        self.on_start_recording_callback = None
        self.on_stop_recording_callback = None
        self.alt_pressed = False
        self.recording_thread = None
        
        # Use either left or right Alt key
        self.trigger_keys = {keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt}
        
        logger.info("PushToTalkHandler initialized for Alt key push-to-talk")
    
    def set_callbacks(self, on_start: Callable, on_stop: Callable):
        """Set callback functions for recording start and stop events."""
        self.on_start_recording_callback = on_start
        self.on_stop_recording_callback = on_stop
        logger.debug("Push-to-talk callbacks set")
    
    def start(self) -> bool:
        """Start the push-to-talk handler."""
        if self.is_running:
            logger.warning("Push-to-talk handler already running")
            return True
        
        try:
            # Create and start the keyboard listener
            self.listener = keyboard.Listener(
                on_press=self._on_key_press,
                on_release=self._on_key_release
            )
            self.listener.start()
            self.is_running = True
            
            logger.info("Push-to-talk handler started successfully")
            logger.info("Hold Alt key to record, release to stop and transcribe")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start push-to-talk handler: {e}")
            return False
    
    def stop(self):
        """Stop the push-to-talk handler."""
        if not self.is_running:
            return
        
        try:
            self.is_running = False
            
            # Stop recording if active
            if self.is_recording:
                self._stop_recording()
            
            # Stop the keyboard listener
            if self.listener:
                self.listener.stop()
                self.listener = None
            
            logger.info("Push-to-talk handler stopped")
            
        except Exception as e:
            logger.error(f"Error stopping push-to-talk handler: {e}")
    
    def _on_key_press(self, key):
        """Handle key press events."""
        try:
            # Debug: Log every key press to see if we're receiving events
            # logger.debug(f"Key pressed: {key}")
            
            # Check if Alt key was pressed
            if key in self.trigger_keys and not self.alt_pressed:
                logger.info(f"Alt key detected: {key}")
                self.alt_pressed = True
                
                # Start recording if not already recording
                if not self.is_recording:
                    self._start_recording()
            
        except Exception as e:
            logger.error(f"Error in key press handler: {e}")
    
    def _on_key_release(self, key):
        """Handle key release events."""
        try:
            # Check if Alt key was released
            if key in self.trigger_keys and self.alt_pressed:
                self.alt_pressed = False
                
                # Stop recording if currently recording
                if self.is_recording:
                    self._stop_recording()
            
            # Stop listener if ESC is pressed (emergency stop)
            if key == keyboard.Key.esc and self.is_recording:
                logger.info("ESC pressed - emergency stop recording")
                self.alt_pressed = False
                self._stop_recording()
            
        except Exception as e:
            logger.error(f"Error in key release handler: {e}")
    
    def _start_recording(self):
        """Start voice recording."""
        if self.is_recording:
            logger.warning("Already recording, ignoring start request")
            return
        
        try:
            self.is_recording = True
            logger.info("Alt key pressed - starting recording")
            logger.log_hotkey_event("Alt", "PRESSED - Recording started")
            
            # Call the start recording callback
            if self.on_start_recording_callback:
                # Run in a separate thread to avoid blocking keyboard listener
                self.recording_thread = threading.Thread(
                    target=self.on_start_recording_callback,
                    daemon=True
                )
                self.recording_thread.start()
            else:
                logger.warning("No start recording callback set")
                
        except Exception as e:
            logger.error(f"Error starting recording: {e}")
            self.is_recording = False
    
    def _stop_recording(self):
        """Stop voice recording and trigger transcription."""
        if not self.is_recording:
            return
        
        try:
            self.is_recording = False
            logger.info("Alt key released - stopping recording and transcribing")
            logger.log_hotkey_event("Alt", "RELEASED - Recording stopped")
            
            # Call the stop recording callback
            if self.on_stop_recording_callback:
                # Run in a separate thread to avoid blocking keyboard listener
                threading.Thread(
                    target=self.on_stop_recording_callback,
                    daemon=True
                ).start()
            else:
                logger.warning("No stop recording callback set")
                
        except Exception as e:
            logger.error(f"Error stopping recording: {e}")
    
    def is_active(self) -> bool:
        """Check if the handler is currently active and listening."""
        return self.is_running and self.listener and self.listener.running
    
    def is_recording_active(self) -> bool:
        """Check if recording is currently active."""
        return self.is_recording



# Global instance removed in favor of Dependency Injection
