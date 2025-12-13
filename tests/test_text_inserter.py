import pytest
from unittest.mock import patch, MagicMock
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
        
        # Mock paste to return something so verification passes
        mock_deps['clip'].paste.return_value = "Hello World"
        
        result = inserter.insert_text("Hello World")
        
        assert result is True
        mock_deps['clip'].copy.assert_called()
        mock_deps['gui'].hotkey.assert_called_with('ctrl', 'v')

    def test_insert_via_keyboard(self, mock_deps):
        """Test keyboard simulation method."""
        # Setup inserter to use keyboard method directly via internal call
        # or mock config to prefer keyboard
        mock_deps['config'].get.side_effect = lambda s, k, f=None: 'keyboard' if k == 'primary_method' else f
        
        inserter = TextInserter()
        result = inserter.insert_text("Hello World")
        
        assert result is True
        mock_deps['gui'].write.assert_called_with("Hello World", interval=0.01)

    def test_insert_via_xdotool(self, mock_deps):
        """Test xdotool method."""
        mock_deps['config'].get.side_effect = lambda s, k, f=None: 'xdotool' if k == 'primary_method' else f
        
        inserter = TextInserter()
        result = inserter.insert_text("Hello World")
        
        assert result is True
        mock_deps['sub'].run.assert_called()
        args = mock_deps['sub'].run.call_args[0][0]
        assert args == ['xdotool', 'type', 'Hello World']

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
