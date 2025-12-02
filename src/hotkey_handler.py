"""
Global hotkey handler for the voice-to-text system.
"""

import subprocess
import threading
import time
import os
import signal
from typing import Optional, Callable
from pathlib import Path

from .utils.logger import logger
from .utils.config_manager import config


class HotkeyHandler:
    """Handles global hotkey detection and management."""
    
    def __init__(self):
        self.hotkey = config.get('General', 'hotkey', 'F5')
        self.xbindkeys_config = Path.home() / ".xbindkeysrc"
        self.is_running = False
        self.callback = None
        self.xbindkeys_process = None
        
        logger.info(f"HotkeyHandler initialized with hotkey: {self.hotkey}")
    
    def set_callback(self, callback: Callable):
        """Set the callback function to be called when hotkey is pressed."""
        self.callback = callback
        logger.debug("Hotkey callback set")
    
    def start(self) -> bool:
        """Start the hotkey handler."""
        if self.is_running:
            logger.warning("Hotkey handler already running")
            return True
        
        try:
            # Create xbindkeys configuration
            if not self._create_xbindkeys_config():
                logger.error("Failed to create xbindkeys configuration")
                return False
            
            # Start xbindkeys
            if not self._start_xbindkeys():
                logger.error("Failed to start xbindkeys")
                return False
            
            # Start monitoring thread
            self.is_running = True
            self._monitor_thread = threading.Thread(target=self._monitor_xbindkeys, daemon=True)
            self._monitor_thread.start()
            
            logger.info("Hotkey handler started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start hotkey handler: {e}")
            return False
    
    def stop(self):
        """Stop the hotkey handler."""
        if not self.is_running:
            return
        
        try:
            self.is_running = False
            
            # Stop xbindkeys process
            if self.xbindkeys_process:
                self.xbindkeys_process.terminate()
                self.xbindkeys_process.wait(timeout=5)
                self.xbindkeys_process = None
            
            # Kill any remaining xbindkeys processes
            subprocess.run(['pkill', 'xbindkeys'], capture_output=True)
            
            logger.info("Hotkey handler stopped")
            
        except Exception as e:
            logger.error(f"Error stopping hotkey handler: {e}")
    
    def _create_xbindkeys_config(self) -> bool:
        """Create xbindkeys configuration file."""
        try:
            # Get the script path for the hotkey command
            script_path = Path(__file__).parent.parent / "scripts" / "hotkey_trigger.sh"
            
            # Create the configuration content
            config_content = f"""# Voice-to-Text System Hotkey Configuration
# Generated automatically - do not edit manually

# F5 hotkey for voice-to-text
"{script_path}"
    {self.hotkey}

# End of configuration
"""
            
            # Write configuration file
            with open(self.xbindkeys_config, 'w') as f:
                f.write(config_content)
            
            logger.debug(f"xbindkeys configuration created: {self.xbindkeys_config}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create xbindkeys config: {e}")
            return False
    
    def _start_xbindkeys(self) -> bool:
        """Start xbindkeys process."""
        try:
            # Kill any existing xbindkeys processes
            subprocess.run(['pkill', 'xbindkeys'], capture_output=True)
            time.sleep(0.5)
            
            # Start xbindkeys
            self.xbindkeys_process = subprocess.Popen(
                ['xbindkeys', '-n', '-f', str(self.xbindkeys_config)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait a moment to ensure it started
            time.sleep(1)
            
            # Check if process is still running
            if self.xbindkeys_process.poll() is None:
                logger.debug("xbindkeys started successfully")
                return True
            else:
                logger.error("xbindkeys failed to start")
                return False
                
        except Exception as e:
            logger.error(f"Failed to start xbindkeys: {e}")
            return False
    
    def _monitor_xbindkeys(self):
        """Monitor xbindkeys process and handle hotkey events."""
        while self.is_running:
            try:
                # Check if xbindkeys is still running
                if self.xbindkeys_process and self.xbindkeys_process.poll() is not None:
                    logger.warning("xbindkeys process died, restarting...")
                    if not self._start_xbindkeys():
                        logger.error("Failed to restart xbindkeys")
                        break
                
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in xbindkeys monitor: {e}")
                time.sleep(1)
    
    def handle_hotkey_press(self):
        """Handle hotkey press event."""
        try:
            logger.log_hotkey_event(self.hotkey, "PRESSED")
            
            if self.callback:
                # Run callback in a separate thread to avoid blocking
                threading.Thread(target=self.callback, daemon=True).start()
            else:
                logger.warning("No hotkey callback set")
                
        except Exception as e:
            logger.error(f"Error handling hotkey press: {e}")
    
    def update_hotkey(self, new_hotkey: str) -> bool:
        """Update the hotkey configuration."""
        try:
            self.hotkey = new_hotkey
            
            # Update configuration
            config.update_hotkey(new_hotkey)
            
            # Restart xbindkeys with new configuration
            if self.is_running:
                self.stop()
                time.sleep(1)
                return self.start()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update hotkey: {e}")
            return False
    
    def get_available_hotkeys(self) -> list:
        """Get list of available hotkeys."""
        return [
            'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12',
            'F13', 'F14', 'F15', 'F16', 'F17', 'F18', 'F19', 'F20', 'F21', 'F22', 'F23', 'F24'
        ]
    
    def test_hotkey(self) -> bool:
        """Test if the current hotkey is working."""
        try:
            # Create a test configuration
            test_config = Path.home() / ".xbindkeysrc.test"
            
            test_content = f"""# Test configuration
"echo 'Hotkey test successful'"
    {self.hotkey}
"""
            
            with open(test_config, 'w') as f:
                f.write(test_content)
            
            # Start xbindkeys with test config
            process = subprocess.Popen(
                ['xbindkeys', '-f', str(test_config)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            time.sleep(1)
            
            # Clean up
            process.terminate()
            process.wait()
            test_config.unlink()
            
            return process.poll() is None
            
        except Exception as e:
            logger.error(f"Hotkey test failed: {e}")
            return False
    
    def get_status(self) -> dict:
        """Get the current status of the hotkey handler."""
        return {
            'running': self.is_running,
            'hotkey': self.hotkey,
            'xbindkeys_running': self.xbindkeys_process is not None and self.xbindkeys_process.poll() is None,
            'config_file': str(self.xbindkeys_config)
        }


# Global hotkey handler instance
hotkey_handler = HotkeyHandler()
