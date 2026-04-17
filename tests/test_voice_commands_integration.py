"""Integration tests for voice_commands.py wired into VoiceTyperWhisper."""

import sys
from unittest.mock import MagicMock, patch

import pytest

# Stub heavy deps so tests run on minimal CI.
sys.modules.setdefault("pyperclip", MagicMock())
sys.modules.setdefault("pyautogui", MagicMock())
sys.modules.setdefault("pynput", MagicMock())
sys.modules.setdefault("pynput.keyboard", MagicMock())
sys.modules.setdefault("pyaudio", MagicMock())
sys.modules.setdefault("silero_vad", MagicMock())
_fw_stub = MagicMock()
_fw_stub.WhisperModel = MagicMock()
sys.modules.setdefault("faster_whisper", _fw_stub)


def _make_typer():
    """Construct a VoiceTyperWhisper with heavy deps mocked."""
    import voice_typer_whisper as vtw
    with patch.object(vtw, "WhisperTranscriber"), \
         patch.object(vtw, "SileroVAD"), \
         patch.object(vtw.keyboard, "Listener"), \
         patch.object(vtw, "signal"):
        return vtw.VoiceTyperWhisper()


# ---------- wake phrase aliases ----------

def test_command_processor_accepts_multiple_wake_phrases():
    from voice_commands import VoiceCommandProcessor, VoiceCommand
    p = VoiceCommandProcessor(prefixes=["computer", "hey computer", "ok computer"])
    assert p.process("computer stop listening") == VoiceCommand.STOP_LISTENING
    assert p.process("hey computer scratch that") == VoiceCommand.CLEAR_LAST
    assert p.process("ok computer help") == VoiceCommand.HELP
    assert p.process("just a normal sentence") is None


def test_command_processor_strips_trailing_punctuation():
    from voice_commands import VoiceCommandProcessor, VoiceCommand
    p = VoiceCommandProcessor(prefixes=["computer"])
    assert p.process("computer help.") == VoiceCommand.HELP
    assert p.process("computer stop listening!") == VoiceCommand.STOP_LISTENING


# ---------- integration: command intercepts before typing ----------

def test_stop_listening_command_pauses_flag_and_skips_type():
    vt = _make_typer()
    fake_inserter = MagicMock()
    vt._text_inserter = fake_inserter
    vt._listening_flag.set()  # ensure listening is on

    # Simulate transcriber returning the command phrase
    vt._transcriber.transcribe = MagicMock(return_value="computer stop listening")

    vt._transcribe_and_type(b"fakeaudio")

    assert not vt._listening_flag.is_set(), "stop-listening command should clear the flag"
    fake_inserter.insert_text.assert_not_called()


def test_scratch_that_sends_ctrl_z():
    vt = _make_typer()
    vt._transcriber.transcribe = MagicMock(return_value="computer scratch that")
    vt._listening_flag.set()

    with patch("voice_typer_whisper.subprocess.run") as mock_run:
        vt._transcribe_and_type(b"fakeaudio")

    # Assert xdotool ctrl+z was sent
    calls = [c for c in mock_run.call_args_list if "ctrl+z" in str(c)]
    assert len(calls) == 1, f"expected one ctrl+z call, got {mock_run.call_args_list}"


def test_help_command_uses_notify_send_not_type():
    vt = _make_typer()
    fake_inserter = MagicMock()
    vt._text_inserter = fake_inserter
    vt._transcriber.transcribe = MagicMock(return_value="computer help")
    vt._listening_flag.set()

    with patch("voice_typer_whisper.subprocess.run") as mock_run:
        vt._transcribe_and_type(b"fakeaudio")

    # notify-send called; insert_text NOT called
    notify_calls = [c for c in mock_run.call_args_list if "notify-send" in str(c)]
    assert len(notify_calls) == 1, f"expected one notify-send call, got {mock_run.call_args_list}"
    fake_inserter.insert_text.assert_not_called()


def test_non_command_transcription_types_normally():
    vt = _make_typer()
    fake_inserter = MagicMock()
    vt._text_inserter = fake_inserter
    vt._transcriber.transcribe = MagicMock(return_value="hello world")
    vt._listening_flag.set()

    vt._transcribe_and_type(b"fakeaudio")

    fake_inserter.insert_text.assert_called_once_with("hello world ")
    # _last_typed_text should be set so scratch-that knows what was typed
    assert vt._last_typed_text == "hello world "


# ---------- H2 race guard: listening disabled between transcribe and type ----------

def test_listening_disabled_mid_transcribe_drops_text():
    vt = _make_typer()
    fake_inserter = MagicMock()
    vt._text_inserter = fake_inserter
    vt._listening_flag.clear()  # simulate paused
    vt._ptt_active = False
    vt._transcriber.transcribe = MagicMock(return_value="some text")

    vt._transcribe_and_type(b"fakeaudio")

    fake_inserter.insert_text.assert_not_called()


def test_start_listening_command_works_when_listening_is_off():
    """Critical: 'computer start listening' must fire even when paused,
    otherwise the user can never resume after a 'stop listening' command.
    Commands reach this path via Alt-PTT (the PTT buffer bypasses the
    listening flag in _on_audio_chunk)."""
    vt = _make_typer()
    vt._listening_flag.clear()  # paused
    vt._transcriber.transcribe = MagicMock(return_value="computer start listening")

    vt._transcribe_and_type(b"fakeaudio")

    assert vt._listening_flag.is_set(), "start-listening command must resume listening even from paused"
