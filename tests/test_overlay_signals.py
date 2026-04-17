"""Tests for listening-overlay state transitions signaled from voice_typer_whisper.

The overlay is mocked so we don't need GTK available in CI.
"""

import sys
from unittest.mock import MagicMock, patch

sys.modules.setdefault("pyperclip", MagicMock())
sys.modules.setdefault("pyautogui", MagicMock())
sys.modules.setdefault("pynput", MagicMock())
sys.modules.setdefault("pynput.keyboard", MagicMock())
sys.modules.setdefault("pyaudio", MagicMock())
sys.modules.setdefault("silero_vad", MagicMock())
_fw_stub = MagicMock()
_fw_stub.WhisperModel = MagicMock()
sys.modules.setdefault("faster_whisper", _fw_stub)


def _make_typer_with_overlay():
    import voice_typer_whisper as vtw
    with patch.object(vtw, "WhisperTranscriber"), \
         patch.object(vtw, "SileroVAD"), \
         patch.object(vtw.keyboard, "Listener"), \
         patch.object(vtw, "signal"):
        vt = vtw.VoiceTyperWhisper()
    vt._overlay = MagicMock()
    return vt, vtw


# ---------- state transitions on VAD events ----------

def test_utterance_start_transitions_overlay_to_speech():
    vt, vtw = _make_typer_with_overlay()
    vt._listening_flag.set()

    vt._process_vad_frame(b"\x00" * 1024, is_speech=True)

    vt._overlay.set_state.assert_called_with(vtw.OverlayState.SPEECH)


def test_utterance_end_transitions_overlay_to_transcribing_when_audio_present():
    vt, vtw = _make_typer_with_overlay()
    vt._listening_flag.set()

    # Enter speech state first
    vt._in_speech = True
    vt._audio_buffer = [b"\x00" * 1024] * 10  # enough frames to exceed min_speech
    vt._speech_frame_count = 10
    vt._silence_frame_count = vt._silence_frames_threshold - 1

    # One more silence frame → end of utterance with enough audio
    vt._process_vad_frame(b"\x00" * 1024, is_speech=False)

    # Should transition to TRANSCRIBING (had enough audio to fire a transcribe)
    calls = [c.args[0] for c in vt._overlay.set_state.call_args_list]
    assert vtw.OverlayState.TRANSCRIBING in calls


def test_stop_listening_command_turns_overlay_off():
    vt, _ = _make_typer_with_overlay()
    vt._listening_flag.set()

    vt._handle_stop_listening()

    # Overlay should be set to OFF and a cmd_ack played
    assert any("OFF" in str(c) or "off" in str(c).lower() for c in vt._overlay.set_state.call_args_list)
    vt._overlay.play_cue.assert_any_call("cmd_ack")


def test_help_command_plays_cmd_ack():
    vt, _ = _make_typer_with_overlay()

    with patch("voice_typer_whisper.subprocess.run"):
        vt._handle_help()

    vt._overlay.play_cue.assert_any_call("cmd_ack")


def test_clear_last_plays_cmd_ack_on_success():
    vt, _ = _make_typer_with_overlay()

    with patch("voice_typer_whisper.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        vt._handle_clear_last()

    vt._overlay.play_cue.assert_any_call("cmd_ack")


def test_clear_last_plays_error_cue_on_failure():
    vt, _ = _make_typer_with_overlay()

    with patch("voice_typer_whisper.subprocess.run", side_effect=RuntimeError("xdotool gone")):
        vt._handle_clear_last()

    vt._overlay.play_cue.assert_any_call("error")


# ---------- audio_cues feature flag ----------

def test_overlay_play_cue_skipped_when_audio_cues_disabled():
    from src.listening_overlay import ListeningOverlay
    overlay = ListeningOverlay(audio_cues=False)
    with patch("src.listening_overlay.subprocess.Popen") as mock_popen:
        overlay.play_cue("listen_start")
    mock_popen.assert_not_called()
