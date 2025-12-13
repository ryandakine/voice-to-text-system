import sys
from unittest.mock import MagicMock

# Mock whisper and pynput modules before importing app code that depends on them
sys.modules["whisper"] = MagicMock()
sys.modules["pynput"] = MagicMock()
sys.modules["pynput.keyboard"] = MagicMock()

import pytest
import time
import threading

from src.application import VoiceToTextApp
from src.interfaces import TranscriptionService, OutputService
from src.input_strategy import InputStrategy

class TestVoiceToTextApp:
    
    @pytest.fixture
    def mock_services(self):
        transcription = MagicMock(spec=TranscriptionService)
        output = MagicMock(spec=OutputService)
        input_strategy = MagicMock(spec=InputStrategy)
        audio_manager = MagicMock()
        
        return {
            'transcription': transcription,
            'output': output,
            'input': input_strategy,
            'audio': audio_manager
        }

    def test_initialization(self, mock_services):
        app = VoiceToTextApp(
            mock_services['transcription'],
            mock_services['output'],
            mock_services['input'],
            mock_services['audio']
        )
        assert app.running is False
        assert app.audio_manager == mock_services['audio']

    def test_start_app(self, mock_services):
        app = VoiceToTextApp(
            mock_services['transcription'],
            mock_services['output'],
            mock_services['input'],
            mock_services['audio']
        )
        
        # Mock input strategy start to return True
        mock_services['input'].start.return_value = True
        
        # We need to run start() in a thread because it blocks
        def stop_app_soon():
            time.sleep(0.1)
            app.stop()
            
        stopper = threading.Thread(target=stop_app_soon)
        stopper.start()
        
        app.start()
        stopper.join()
        
        mock_services['input'].start.assert_called_once()
        # app.stop() should call strategy.stop()
        mock_services['input'].stop.assert_called_once()

    def test_recording_flow(self, mock_services):
        app = VoiceToTextApp(
            mock_services['transcription'],
            mock_services['output'],
            mock_services['input'],
            mock_services['audio']
        )
        
        # Simulate Start Recording
        app.start_recording()
        mock_services['audio'].start_recording.assert_called_once()
        
        # Simulate Stop Recording -> Returns audio file
        mock_services['audio'].stop_recording.return_value = "/tmp/test.wav"
        mock_services['transcription'].transcribe_audio.return_value = "Hello World"
        mock_services['output'].insert_text.return_value = True
        
        app.stop_recording()
        
        # Wait for background processing thread
        # In a real test we might want to join the thread, but we can just sleep briefly 
        # as we are mocking synchronous calls
        time.sleep(0.2)
        
        mock_services['transcription'].transcribe_audio.assert_called_with("/tmp/test.wav")
        mock_services['output'].insert_text.assert_called_with("Hello World")

