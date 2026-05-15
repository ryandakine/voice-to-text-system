"""Audio device management for VoiceTyper.

Allows selection and configuration of audio input devices.
"""

import pyaudio
from typing import List, Dict, Optional, Tuple
import logging


class AudioDeviceManager:
    """Manages audio input devices."""
    
    def __init__(self):
        self.pa = pyaudio.PyAudio()
        self._selected_device: Optional[int] = None
        
    def list_input_devices(self) -> List[Dict]:
        """List all available input devices."""
        devices = []
        
        for i in range(self.pa.get_device_count()):
            info = self.pa.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:  # Input device
                devices.append({
                    'index': i,
                    'name': info['name'],
                    'channels': info['maxInputChannels'],
                    'sample_rate': int(info['defaultSampleRate']),
                    'latency': info['defaultLowInputLatency'],
                })
        
        return devices
    
    def get_default_input_device(self) -> Optional[Dict]:
        """Get the default input device."""
        try:
            default_index = self.pa.get_default_input_device_info()['index']
            return self.get_device_info(default_index)
        except:
            return None
    
    def get_device_info(self, device_index: int) -> Optional[Dict]:
        """Get info for a specific device."""
        try:
            info = self.pa.get_device_info_by_index(device_index)
            return {
                'index': device_index,
                'name': info['name'],
                'channels': info['maxInputChannels'],
                'sample_rate': int(info['defaultSampleRate']),
            }
        except:
            return None
    
    def select_device(self, device_index: int) -> bool:
        """Select a device by index."""
        info = self.get_device_info(device_index)
        if info:
            self._selected_device = device_index
            logging.info(f"Selected audio device: {info['name']}")
            return True
        return False
    
    def select_by_name(self, name_pattern: str) -> bool:
        """Select a device by name pattern (partial match)."""
        for device in self.list_input_devices():
            if name_pattern.lower() in device['name'].lower():
                return self.select_device(device['index'])
        return False
    
    @property
    def selected_device(self) -> Optional[int]:
        """Get the currently selected device index."""
        return self._selected_device
    
    def get_recommended_device(self) -> Optional[Dict]:
        """Get recommended device (prefer USB mics over built-in)."""
        devices = self.list_input_devices()
        
        # First try to find USB microphone
        for d in devices:
            if 'usb' in d['name'].lower():
                return d
        
        # Then try to find external mic
        for d in devices:
            if any(x in d['name'].lower() for x in ['mic', 'microphone', 'external']):
                return d
        
        # Fall back to default
        return self.get_default_input_device()
    
    def print_device_list(self) -> None:
        """Print a formatted list of devices."""
        print("\nAvailable Audio Input Devices:")
        print("-" * 50)
        
        for device in self.list_input_devices():
            selected = " <- SELECTED" if device['index'] == self._selected_device else ""
            print(f"  [{device['index']}] {device['name']}")
            print(f"      Channels: {device['channels']}, Sample Rate: {device['sample_rate']}Hz{selected}")
        
        print("-" * 50)
    
    def __del__(self):
        """Cleanup."""
        if hasattr(self, 'pa'):
            self.pa.terminate()


def test_devices():
    """Test audio device listing."""
    manager = AudioDeviceManager()
    manager.print_device_list()
    
    recommended = manager.get_recommended_device()
    if recommended:
        print(f"\nRecommended device: {recommended['name']}")


if __name__ == "__main__":
    test_devices()
