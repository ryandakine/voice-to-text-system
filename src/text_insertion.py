"""
Text insertion module for universal text input across applications.
"""

import subprocess
import time
import threading
from typing import Optional, List
import pyautogui
import pyperclip

from .utils.logger import logger
from .utils.config_manager import config


from .interfaces import OutputService

class TextInserter(OutputService):
    """Handles universal text insertion across different applications."""
    
    def __init__(self):
        self.primary_method = config.get('TextInsertion', 'primary_method', 'clipboard')
        self.fallback_method = config.get('TextInsertion', 'fallback_method', 'keyboard')
        self.delay_before_insert = config.getfloat('TextInsertion', 'delay_before_insert', 0.1)
        self.clear_clipboard_after = config.getboolean('TextInsertion', 'clear_clipboard_after', True)
        self.supported_apps = config.get('TextInsertion', 'supported_apps', '').split(',')
        if not self.supported_apps or self.supported_apps == ['']:
             # Fallback default if empty
             self.supported_apps = [
                'firefox', 'chrome', 'chromium', 'brave',
                'code', 'code-oss', 'sublime_text',
                'gedit', 'mousepad', 'leafpad',
                'libreoffice', 'libreoffice-writer',
                'terminal', 'gnome-terminal', 'xfce4-terminal',
                'konsole', 'tilix', 'terminator'
             ]
        
        # Store original clipboard content
        self.original_clipboard = ""
        
        logger.info("TextInserter initialized")
    
    def insert_text(self, text: str) -> bool:
        """Insert text using the configured method."""
        if not text or not text.strip():
            logger.warning("Attempted to insert empty text")
            return False
        
        try:
            # Try primary method first
            if self._insert_with_method(text, self.primary_method):
                return True
            
            # Fall back to secondary method
            if self._insert_with_method(text, self.fallback_method):
                return True
            
            logger.error("All text insertion methods failed")
            return False
            
        except Exception as e:
            logger.error(f"Text insertion failed: {e}")
            return False
    
    def _insert_with_method(self, text: str, method: str) -> bool:
        """Insert text using a specific method."""
        try:
            if method == 'clipboard':
                return self._insert_via_clipboard(text)
            elif method == 'keyboard':
                return self._insert_via_keyboard(text)
            elif method == 'xdotool':
                return self._insert_via_xdotool(text)
            else:
                logger.error(f"Unknown insertion method: {method}")
                return False
                
        except Exception as e:
            logger.error(f"Method {method} failed: {e}")
            return False
    
    def _insert_via_clipboard(self, text: str) -> bool:
        """Insert text using clipboard method."""
        try:
            # Store original clipboard content
            try:
                self.original_clipboard = pyperclip.paste()
            except:
                self.original_clipboard = ""
            
            # Clear clipboard first to prevent old paste
            pyperclip.copy("")
            time.sleep(0.05)
            
            # Set new text to clipboard
            pyperclip.copy(text)
            
            # Wait for clipboard to update
            time.sleep(0.15)
            
            # Verify clipboard has the correct content
            current_clip = pyperclip.paste()
            if current_clip != text:
                logger.warning(f"Clipboard verification failed. Expected: {text[:50]}, Got: {current_clip[:50]}")
            
            # Simulate Ctrl+V paste
            pyautogui.hotkey('ctrl', 'v')
            
            # Wait for paste to complete
            time.sleep(0.2)
            
            # Clear clipboard immediately to prevent re-pasting old content
            pyperclip.copy("")
            time.sleep(0.05)
            
            # Restore original clipboard if configured and it wasn't empty
            if self.clear_clipboard_after and self.original_clipboard:
                pyperclip.copy(self.original_clipboard)
            
            logger.log_text_insertion("clipboard", True, f"length={len(text)}")
            return True
            
        except Exception as e:
            logger.error(f"Clipboard insertion failed: {e}")
            # Try to restore clipboard
            try:
                if self.original_clipboard:
                    pyperclip.copy(self.original_clipboard)
            except:
                pass
            return False
    
    def _insert_via_keyboard(self, text: str) -> bool:
        """Insert text using keyboard simulation."""
        try:
            # Type the text directly
            pyautogui.write(text, interval=0.01)  # Small delay between characters
            
            logger.log_text_insertion("keyboard", True, f"length={len(text)}")
            return True
            
        except Exception as e:
            logger.error(f"Keyboard insertion failed: {e}")
            return False
    
    def _insert_via_xdotool(self, text: str) -> bool:
        """Insert text using xdotool."""
        try:
            # Use xdotool to type text
            subprocess.run(['xdotool', 'type', text], check=True)
            
            logger.log_text_insertion("xdotool", True, f"length={len(text)}")
            return True
            
        except Exception as e:
            logger.error(f"xdotool insertion failed: {e}")
            return False
    
    def insert_text_at_position(self, text: str, x: int, y: int) -> bool:
        """Insert text at specific screen coordinates."""
        try:
            # Move mouse to position
            pyautogui.moveTo(x, y)
            time.sleep(0.1)
            
            # Click to focus
            pyautogui.click()
            time.sleep(0.1)
            
            # Insert text
            return self.insert_text(text)
            
        except Exception as e:
            logger.error(f"Position-based insertion failed: {e}")
            return False
    
    def insert_text_in_active_window(self, text: str) -> bool:
        """Insert text in the currently active window."""
        try:
            # Ensure window is focused
            pyautogui.click()
            time.sleep(0.1)
            
            # Insert text
            return self.insert_text(text)
            
        except Exception as e:
            logger.error(f"Active window insertion failed: {e}")
            return False
    
    def get_active_window_info(self) -> Optional[dict]:
        """Get information about the currently active window."""
        try:
            # Use xdotool to get active window info
            result = subprocess.run(
                ['xdotool', 'getactivewindow', 'getwindowgeometry'],
                capture_output=True, text=True, check=True
            )
            
            # Parse output
            lines = result.stdout.strip().split('\n')
            if len(lines) >= 2:
                window_id = lines[0].split()[-1]
                geometry = lines[1].split()[-1]
                
                return {
                    'window_id': window_id,
                    'geometry': geometry
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get active window info: {e}")
            return None
    
    def get_supported_applications(self) -> List[str]:
        """Get list of applications that work well with text insertion."""
        return self.supported_apps
    
    def test_insertion_methods(self) -> dict:
        """Test all insertion methods and return results."""
        test_text = "Test insertion"
        results = {}
        
        for method in ['clipboard', 'keyboard', 'xdotool']:
            try:
                # Create a temporary text file for testing
                with open('/tmp/test_insertion.txt', 'w') as f:
                    f.write("")
                
                # Open text editor
                subprocess.Popen(['gedit', '/tmp/test_insertion.txt'])
                time.sleep(1)
                
                # Test insertion
                success = self._insert_with_method(test_text, method)
                results[method] = success
                
                # Close editor
                subprocess.run(['pkill', 'gedit'])
                
            except Exception as e:
                results[method] = False
                logger.error(f"Test failed for {method}: {e}")
        
        return results
    
    def update_insertion_method(self, primary: str, fallback: str = None):
        """Update the text insertion method."""
        if primary not in ['clipboard', 'keyboard', 'xdotool']:
            logger.error(f"Invalid primary method: {primary}")
            return
        
        self.primary_method = primary
        config.set('TextInsertion', 'primary_method', primary)
        
        if fallback and fallback in ['clipboard', 'keyboard', 'xdotool']:
            self.fallback_method = fallback
            config.set('TextInsertion', 'fallback_method', fallback)
        
        config.save_config()
        logger.info(f"Insertion method updated: primary={primary}, fallback={self.fallback_method}")
    
    def set_delay(self, delay: float):
        """Set the delay before text insertion."""
        self.delay_before_insert = delay
        config.set('TextInsertion', 'delay_before_insert', str(delay))
        config.save_config()
        logger.info(f"Insertion delay updated to: {delay}s")



# Global instance removed in favor of Dependency Injection
