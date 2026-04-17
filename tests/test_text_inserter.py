import pytest
from unittest.mock import patch, MagicMock
import sys

# Mock pynput and whisper to prevent import errors in CI env
sys.modules["pynput"] = MagicMock()
sys.modules["pynput.keyboard"] = MagicMock()
sys.modules["whisper"] = MagicMock()
sys.modules["pyautogui"] = MagicMock()
sys.modules["pyperclip"] = MagicMock()
import time

from src.text_insertion import TextInserter

class TestTextInserter:
    @pytest.fixture
    def mock_deps(self):
        """Mock external dependencies."""
        with patch('src.text_insertion.pyautogui') as mock_gui, \
             patch('src.text_insertion.pyperclip') as mock_clip, \
             patch('src.text_insertion.subprocess') as mock_sub, \
             patch('src.text_insertion.config') as mock_config:
            
            # Configure mock config defaults
            mock_config.get.side_effect = lambda s, k, f=None: f
            mock_config.getfloat.return_value = 0.0
            mock_config.getboolean.return_value = True
            
            yield {
                'gui': mock_gui,
                'clip': mock_clip,
                'sub': mock_sub,
                'config': mock_config
            }

    def test_insert_via_clipboard(self, mock_deps):
        """Test clipboard insertion method."""
        mock_deps['config'].get.return_value = 'clipboard'  # primary method

        inserter = TextInserter()
        mock_deps['clip'].paste.return_value = "Hello World"

        result = inserter.insert_text("Hello World")

        assert result is True
        # Clipboard path copies the text to clipboard (and later restores/clears).
        mock_deps['clip'].copy.assert_any_call("Hello World")

    def test_insert_via_keyboard(self, mock_deps):
        """Test keyboard simulation method."""
        mock_deps['config'].get.side_effect = lambda s, k, f=None: 'keyboard' if k == 'primary_method' else f

        inserter = TextInserter()
        result = inserter.insert_text("Hello World")

        assert result is True
        # pyautogui.write is called with the text; interval comes from config (default 0.0)
        mock_deps['gui'].write.assert_called_once()
        call_args, call_kwargs = mock_deps['gui'].write.call_args
        assert call_args[0] == "Hello World"

    def test_insert_via_xdotool(self, mock_deps):
        """Test xdotool method."""
        mock_deps['config'].get.side_effect = lambda s, k, f=None: 'xdotool' if k == 'primary_method' else f

        inserter = TextInserter()
        result = inserter.insert_text("Hello World")

        assert result is True
        mock_deps['sub'].run.assert_called()
        args = mock_deps['sub'].run.call_args[0][0]
        # Real command: ['xdotool', 'type', '--clearmodifiers', '--delay', '0', '--', 'Hello World']
        assert args[0] == 'xdotool'
        assert 'type' in args
        assert 'Hello World' in args

    def test_fallback_mechanism(self, mock_deps):
        """Test correct fallback behavior when primary fails."""
        # Primary: clipboard (fails), Fallback: keyboard
        def config_get(section, key, fallback=None):
            if key == 'primary_method': return 'clipboard'
            if key == 'fallback_method': return 'keyboard'
            return fallback
        
        mock_deps['config'].get.side_effect = config_get
        
        # Make clipboard insertion fail
        mock_deps['clip'].copy.side_effect = Exception("Clipboard broken")
        
        inserter = TextInserter()
        result = inserter.insert_text("Hello World")
        
        # Should succeed via fallback
        assert result is True
        # Verify both methods were attempted
        mock_deps['clip'].copy.assert_called() # Primary
        mock_deps['gui'].write.assert_called() # Fallback
