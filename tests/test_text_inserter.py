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
             patch('src.text_insertion.config') as mock_config, \
             patch('src.text_insertion.wait_for_modifiers_released', return_value=True) as mock_wait:

            # Configure mock config defaults
            mock_config.get.side_effect = lambda s, k, f=None: f
            mock_config.getfloat.return_value = 0.0
            mock_config.getboolean.return_value = True

            yield {
                'gui': mock_gui,
                'clip': mock_clip,
                'sub': mock_sub,
                'config': mock_config,
                'wait': mock_wait,
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
        # Real command: ['xdotool', 'type', '--delay', '0', '--', 'Hello World']
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

    @pytest.mark.parametrize('method', ['keyboard', 'xdotool'])
    def test_typing_dismisses_alt_menu_before_sending_text(self, mock_deps, method):
        inserter = TextInserter()
        inserter.primary_method = method
        with patch.object(inserter, '_get_active_window_class', return_value='antigravity ide'), \
             patch('src.text_insertion.shutil.which', return_value='/usr/bin/xdotool'):
            assert inserter.insert_text('Voice typing works.') is True

        mock_deps['sub'].run.assert_any_call(
            ['xdotool', 'key', 'Escape'],
            capture_output=True, check=True, timeout=5,
        )

    @pytest.mark.parametrize('method', ['clipboard', 'keyboard', 'xdotool'])
    def test_no_insertion_path_releases_and_represses_held_keys(self, mock_deps, method):
        """xdotool --clearmodifiers fakes a release of every held modifier (ending an
        Alt push-to-talk mid-hold) and re-presses it, which can leave Super/Alt stuck.
        No insertion path may ever ask for it."""
        inserter = TextInserter()
        inserter.primary_method = method
        with patch.object(inserter, '_get_active_window_class', return_value='google-chrome'), \
             patch('src.text_insertion.shutil.which', return_value='/usr/bin/xdotool'):
            assert inserter.insert_text('Voice typing works.', window_id='0x1') is True

        argvs = [c.args[0] for c in mock_deps['sub'].run.call_args_list if c.args]
        assert argvs, 'expected at least one xdotool call'
        assert not any('--clearmodifiers' in argv for argv in argvs), argvs

    @pytest.mark.parametrize('method, injection', [
        ('keyboard', 'type text'),
        ('xdotool', 'xdotool type --delay 0 -- hi'),
        ('clipboard', 'xdotool key ctrl+v'),
    ])
    def test_waits_for_held_keys_to_be_released_before_injecting(self, mock_deps, method, injection):
        """Keys are injected only after the user lets go of every modifier, never during."""
        order = []
        mock_deps['wait'].side_effect = lambda *a, **k: order.append('wait') or True
        mock_deps['sub'].run.side_effect = lambda argv, **k: order.append(' '.join(argv)) or MagicMock()
        mock_deps['gui'].write.side_effect = lambda *a, **k: order.append('type text')
        mock_deps['clip'].paste.return_value = 'hi'
        inserter = TextInserter()
        inserter.primary_method = method
        with patch.object(inserter, '_get_active_window_class', return_value='google-chrome'), \
             patch('src.text_insertion.shutil.which', return_value='/usr/bin/xdotool'):
            assert inserter.insert_text('hi') is True

        injections = [i for i, step in enumerate(order) if step in ('xdotool key Escape', injection)]
        assert injections, order
        for i in injections:
            assert i > 0 and order[i - 1] == 'wait', order

    def test_held_modifier_after_timeout_aborts_every_method_and_notifies_once(self, mock_deps):
        """Typing anyway with Alt/Ctrl still down fires shortcuts. Tell the user, type nothing."""
        mock_deps['wait'].return_value = False
        inserter = TextInserter()
        for method in ('clipboard', 'keyboard', 'xdotool'):
            inserter.primary_method = method
            assert inserter.insert_text('hi') is False

        mock_deps['gui'].write.assert_not_called()
        mock_deps['clip'].copy.assert_not_called()
        mock_deps['sub'].run.assert_called_with(
            ['notify-send', 'Voice Typer',
             'A modifier key stayed held - dictation not typed'],
            timeout=5, check=False,
        )
        assert mock_deps['sub'].run.call_count == 3

    def test_terminal_typing_preserves_escape_key(self, mock_deps):
        inserter = TextInserter()
        inserter.primary_method = 'keyboard'
        with patch.object(inserter, '_get_active_window_class', return_value='gnome-terminal'), \
             patch('src.text_insertion.shutil.which', return_value='/usr/bin/xdotool'):
            assert inserter.insert_text('Voice typing works.') is True
        mock_deps['sub'].run.assert_not_called()

    def test_window_id_ignores_xdotool_diagnostics(self, mock_deps):
        inserter = TextInserter()
        mock_deps['sub'].run.return_value.stdout = 'command: getactivewindow\n176160772\n'
        assert inserter._get_active_window_id() == '176160772'

    def test_terminal_class_uses_supported_x11_property(self, mock_deps):
        inserter = TextInserter()
        mock_deps['sub'].run.side_effect = [
            MagicMock(stdout='command: getactivewindow\n123\n'),
            MagicMock(stdout='WM_CLASS(STRING) = "gnome-terminal-server", "Gnome-terminal"\n'),
        ]
        assert inserter._get_paste_hotkey() == ['ctrl', 'shift', 'v']
