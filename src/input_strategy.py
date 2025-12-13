from typing import Protocol, Callable, Optional
import threading
from .hotkey_handler import HotkeyHandler
from .push_to_talk_handler import PushToTalkHandler
from .utils.logger import logger

class InputStrategy(Protocol):
    """Protocol for input strategies (e.g. Hotkey toggle, Push-to-Talk)."""
    
    def start(self, on_start_recording: Callable, on_stop_recording: Callable) -> bool:
        """Start listening for input."""
        ...

    def stop(self):
        """Stop listening for input."""
        ...

class HotkeyInputStrategy:
    """Strategy for toggling recording via a global hotkey."""
    
    def __init__(self, hotkey_handler: HotkeyHandler):
        self.handler = hotkey_handler
        self.is_recording = False
        self._on_start = None
        self._on_stop = None

    def start(self, on_start_recording: Callable, on_stop_recording: Callable) -> bool:
        self._on_start = on_start_recording
        self._on_stop = on_stop_recording
        
        # Determine behavior: Toggle
        def toggle_callback():
            if self.is_recording:
                self.is_recording = False
                if self._on_stop: self._on_stop()
            else:
                self.is_recording = True
                if self._on_start: self._on_start()
                
        self.handler.set_callback(toggle_callback)
        return self.handler.start()

    def stop(self):
        self.handler.stop()

class PTTInputStrategy:
    """Strategy for Push-to-Talk (Hold key to record)."""
    
    def __init__(self, ptt_handler: PushToTalkHandler):
        self.handler = ptt_handler

    def start(self, on_start_recording: Callable, on_stop_recording: Callable) -> bool:
        self.handler.set_callbacks(on_start_recording, on_stop_recording)
        return self.handler.start()

    def stop(self):
        self.handler.stop()
