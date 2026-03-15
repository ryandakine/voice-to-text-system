"""Audio device management for VoiceTyper."""
import pyaudio
from typing import List, Dict, Optional, Tuple
import logging


class AudioManager:
    """Manages audio input devices."""
    
    def __init__(self):
        self.pa = pyaudio.PyAudio()
        self._selected_device: Optional[int] = None
        
    def list_devices(self) -> List[Dict]:
        """List all available input devices."""
        devices = []
        
        for i in range(self.pa.get_device_count()):
            try:
                info = self.pa.get_device_info_by_index(i)
                if info['maxInputChannels'] > 0:
                    devices.append({
                        'index': i,
                        'name': info['name'],
                        'channels': info['maxInputChannels'],
                        'sample_rate': int(info['defaultSampleRate']),
                    })
            except:
                continue
        
        return devices
    
    def print_devices(self) -> None:
        """Print formatted device list."""
        devices = self.list_devices()
        
        print("\n🎤 Available Audio Input Devices:")
        print("-" * 60)
        
        for dev in devices:
            marker = " <- SELECTED" if dev['index'] == self._selected_device else ""
            print(f"  [{dev['index']}] {dev['name']}")
            print(f"      Sample Rate: {dev['sample_rate']}Hz, Channels: {dev['channels']}{marker}")
        
        print("-" * 60)
        print(f"\nTotal devices: {len(devices)}")
    
    def get_default_device(self) -> Optional[int]:
        """Get default input device index."""
        try:
            info = self.pa.get_default_input_device_info()
            return info['index']
        except:
            return None
    
    def select_device(self, device_index: int) -> bool:
        """Select device by index."""
        try:
            info = self.pa.get_device_info_by_index(device_index)
            if info['maxInputChannels'] > 0:
                self._selected_device = device_index
                logging.info(f"Selected audio device [{device_index}]: {info['name']}")
                return True
        except Exception as e:
            logging.error(f"Error selecting device {device_index}: {e}")
        return False
    
    def select_by_name(self, name_pattern: str) -> bool:
        """Select device by name pattern."""
        for dev in self.list_devices():
            if name_pattern.lower() in dev['name'].lower():
                return self.select_device(dev['index'])
        return False
    
    def get_recommended_device(self) -> Optional[int]:
        """Get recommended device (prefer USB/external)."""
        devices = self.list_devices()
        
        # Prefer USB mics
        for dev in devices:
            if 'usb' in dev['name'].lower():
                return dev['index']
        
        # Then external mics
        for dev in devices:
            if any(x in dev['name'].lower() for x in ['mic', 'microphone', 'external']):
                return dev['index']
        
        # Fall back to default
        return self.get_default_device()
    
    def get_selected_device(self) -> Optional[int]:
        """Get selected device index."""
        return self._selected_device
    
    def get_device_info(self, index: Optional[int] = None) -> Optional[Dict]:
        """Get info for selected or specified device."""
        if index is None:
            index = self._selected_device
        if index is None:
            return None
            
        try:
            info = self.pa.get_device_info_by_index(index)
            return {
                'index': index,
                'name': info['name'],
                'channels': info['maxInputChannels'],
                'sample_rate': int(info['defaultSampleRate']),
            }
        except:
            return None
    
    def open_stream(self, format, channels, rate, frames_per_buffer,
                    input_device_index: Optional[int] = None):
        """Open audio stream with selected device."""
        device = input_device_index or self._selected_device or self.get_default_device()
        
        return self.pa.open(
            format=format,
            channels=channels,
            rate=rate,
            input=True,
            input_device_index=device,
            frames_per_buffer=frames_per_buffer,
        )
    
    def __del__(self):
        """Cleanup."""
        if hasattr(self, 'pa'):
            self.pa.terminate()
