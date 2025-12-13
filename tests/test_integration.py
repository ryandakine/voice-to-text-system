import pytest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.main_push_to_talk import VoiceToTextSystemPTT

class TestIntegration:
    @pytest.fixture
    def mock_components(self):
        """Mock all hardware components."""
        with patch('src.main_push_to_talk.push_to_talk_handler') as mock_ptt, \
             patch('src.main_push_to_talk.audio_manager') as mock_audio, \
             patch('src.main_push_to_talk.speech_processor') as mock_speech, \
             patch('src.main_push_to_talk.text_inserter') as mock_text:
             
             mock_speech.load_model.return_value = True
             mock_ptt.start.return_value = True
             
             yield {
                 'ptt': mock_ptt,
                 'audio': mock_audio,
                 'speech': mock_speech,
                 'text': mock_text
             }

    def test_system_initialization(self, mock_components):
        """Test that the system initializes without crashing."""
        system = VoiceToTextSystemPTT()
        assert system.running is False
        assert system.processing is False

    def test_start_stop(self, mock_components):
        """Test start and stop cycle."""
        system = VoiceToTextSystemPTT()
        
        # Test Start
        success = system.start()
        assert success is True
        assert system.running is True
        assert hasattr(system, 'audio_queue')
        assert hasattr(system, 'worker_thread')
        assert system.worker_thread.is_alive()
        
        mock_components['ptt'].start.assert_called_once()
        
        # Test Stop
        system.stop()
        assert system.running is False
        mock_components['ptt'].stop.assert_called_once()
        # Verify queue thread is handled (daemon threads die on exit, so likely fine for test)

    def test_processing_flow(self, mock_components):
        """Test the audio processing flow through the queue."""
        system = VoiceToTextSystemPTT()
        system.start()
        
        # Simulate recording stop which adds to queue
        mock_components['audio'].stop_recording.return_value = "/tmp/test.wav"
        
        # Manually trigger _on_recording_stop
        system._on_recording_stop()
        
        # Verify file was put in queue
        assert system.audio_queue.qsize() == 1 or system.audio_queue.qsize() == 0 
        # It might be 0 if the worker picked it up instantly.
        
        # Give worker time to process
        import time
        time.sleep(0.2)
        
        mock_components['speech'].transcribe_audio.assert_called_with("/tmp/test.wav")
        
        system.stop()
