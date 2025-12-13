"""
Audio utilities for the voice-to-text system.
"""

import pyaudio
import wave
import numpy as np
import tempfile
import os
from typing import List, Dict, Optional, Tuple
from pathlib import Path

from .logger import logger


class AudioManager:
    """Manages audio devices and recording for the voice-to-text system."""
    
    def __init__(self):
        self.pyaudio = pyaudio.PyAudio()
        self.recording = False
        self.stream = None
        self.frames = []
        self.temp_dir = Path(tempfile.gettempdir()) / "voice-to-text"
        self.temp_dir.mkdir(exist_ok=True)
        
        logger.info("AudioManager initialized")
    
    def get_audio_devices(self) -> List[Dict[str, any]]:
        """Get list of available audio input devices."""
        devices = []
        
        try:
            for i in range(self.pyaudio.get_device_count()):
                device_info = self.pyaudio.get_device_info_by_index(i)
                
                # Only include input devices
                if device_info['maxInputChannels'] > 0:
                    devices.append({
                        'index': i,
                        'name': device_info['name'],
                        'channels': device_info['maxInputChannels'],
                        'sample_rate': int(device_info['defaultSampleRate']),
                        'is_default': device_info['index'] == self.pyaudio.get_default_input_device_info()['index']
                    })
            
            logger.debug(f"Found {len(devices)} audio input devices")
            return devices
            
        except Exception as e:
            logger.error(f"Failed to get audio devices: {e}")
            return []
    
    def get_default_device(self) -> Optional[Dict[str, any]]:
        """Get the default audio input device."""
        try:
            default_info = self.pyaudio.get_default_input_device_info()
            return {
                'index': default_info['index'],
                'name': default_info['name'],
                'channels': default_info['maxInputChannels'],
                'sample_rate': int(default_info['defaultSampleRate']),
                'is_default': True
            }
        except Exception as e:
            logger.error(f"Failed to get default audio device: {e}")
            return None
    
    def test_device(self, device_index: int) -> bool:
        """Test if an audio device is working."""
        try:
            device_info = self.pyaudio.get_device_info_by_index(device_index)
            
            # Try to open a test stream
            test_stream = self.pyaudio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=1024
            )
            
            test_stream.close()
            logger.debug(f"Audio device {device_index} test successful")
            return True
            
        except Exception as e:
            logger.error(f"Audio device {device_index} test failed: {e}")
            return False
    
    def start_recording(self, device_index: int = -1, sample_rate: int = 16000) -> bool:
        """Start recording audio from the specified device."""
        if self.recording:
            logger.warning("Recording already in progress")
            return False
        
        try:
            # Use default device if device_index is -1
            if device_index == -1:
                device_index = self.pyaudio.get_default_input_device_info()['index']
            
            self.stream = self.pyaudio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=sample_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=1024,
                stream_callback=self._audio_callback
            )
            
            self.frames = []
            self.recording = True
            
            logger.log_audio_event("RECORDING_STARTED", f"device={device_index}, rate={sample_rate}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            return False
    
    def stop_recording(self) -> Optional[str]:
        """Stop recording and return the path to the saved audio file."""
        if not self.recording:
            logger.warning("No recording in progress")
            return None
        
        try:
            self.recording = False
            
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
                self.stream = None
            
            if not self.frames:
                logger.warning("No audio frames recorded")
                return None
            
            # Save audio to temporary file
            audio_file = self._save_audio_frames()
            
            logger.log_audio_event("RECORDING_STOPPED", f"frames={len(self.frames)}")
            return audio_file
            
        except Exception as e:
            logger.error(f"Failed to stop recording: {e}")
            return None
    
    def _audio_callback(self, in_data, frame_count, time_info, status):
        """Callback for audio stream to collect frames."""
        if self.recording:
            self.frames.append(in_data)
        return (in_data, pyaudio.paContinue)
    
    def _save_audio_frames(self) -> str:
        """Save recorded audio frames to a temporary WAV file."""
        try:
            # Create temporary file
            temp_file = self.temp_dir / f"recording_{os.getpid()}_{len(self.frames)}.wav"
            
            # Save as WAV file
            with wave.open(str(temp_file), 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(self.pyaudio.get_sample_size(pyaudio.paInt16))
                wf.setframerate(16000)
                wf.writeframes(b''.join(self.frames))
            
            logger.debug(f"Audio saved to: {temp_file}")
            return str(temp_file)
            
        except Exception as e:
            logger.error(f"Failed to save audio frames: {e}")
            return ""
    
    def cleanup_temp_files(self):
        """Clean up temporary audio files."""
        try:
            for temp_file in self.temp_dir.glob("recording_*.wav"):
                temp_file.unlink()
            logger.debug("Temporary audio files cleaned up")
        except Exception as e:
            logger.error(f"Failed to cleanup temp files: {e}")
    
    def get_audio_level(self) -> float:
        """Get current audio level (for VU meter)."""
        if not self.recording or not self.frames:
            return 0.0
        
        try:
            # Get the last frame
            last_frame = self.frames[-1]
            
            # Convert to numpy array
            audio_data = np.frombuffer(last_frame, dtype=np.int16)
            
            # Calculate RMS level
            rms = np.sqrt(np.mean(audio_data**2))
            
            # Normalize to 0-1 range
            level = min(1.0, rms / 32768.0)
            
            return level
            
        except Exception as e:
            logger.error(f"Failed to get audio level: {e}")
            return 0.0
    
    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self.recording
    
    def get_recording_duration(self) -> float:
        """Get current recording duration in seconds."""
        if not self.recording:
            return 0.0
        
        # Calculate duration based on number of frames and sample rate
        total_samples = len(self.frames) * 1024  # frames_per_buffer
        return total_samples / 16000.0  # sample_rate
    
    def __del__(self):
        """Cleanup when object is destroyed."""
        try:
            if self.stream:
                self.stream.close()
            if self.pyaudio:
                self.pyaudio.terminate()
        except:
            pass



# Global instance removed in favor of Dependency Injection
