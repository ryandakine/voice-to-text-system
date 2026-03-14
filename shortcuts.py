"""Keyboard shortcut configuration for VoiceTyper.

Allows customization of hotkeys for different actions.
"""

from dataclasses import dataclass
from typing import Optional, Set
from pynput import keyboard


@dataclass
class ShortcutConfig:
    """Configuration for keyboard shortcuts."""
    
    # Toggle listening on/off
    toggle_key: keyboard.Key = keyboard.Key.f8
    
    # Push-to-talk key
    ptt_key: Set[keyboard.Key] = None
    
    # OpenClaw mode toggle
    openclaw_key: keyboard.Key = keyboard.Key.f9
    
    # Emergency stop
    emergency_stop: keyboard.Key = keyboard.Key.esc
    
    def __post_init__(self):
        if self.ptt_key is None:
            self.ptt_key = {keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt}


class ShortcutManager:
    """Manages keyboard shortcuts configuration."""
    
    def __init__(self, config: Optional[ShortcutConfig] = None):
        self.config = config or ShortcutConfig()
        
    def is_toggle(self, key) -> bool:
        """Check if key is the toggle key."""
        return key == self.config.toggle_key
    
    def is_ptt(self, key) -> bool:
        """Check if key is a PTT key."""
        return key in self.config.ptt_key
    
    def is_openclaw(self, key) -> bool:
        """Check if key is the OpenClaw toggle."""
        return key == self.config.openclaw_key
    
    def is_emergency_stop(self, key) -> bool:
        """Check if key is emergency stop."""
        return key == self.config.emergency_stop
