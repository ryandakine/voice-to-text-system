"""Tests for voice_typer_whisper.py — the faster-whisper + Silero VAD path."""

import sys
import subprocess
import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# Stub heavy deps so tests run under plain system pytest too (no venv required).
sys.modules.setdefault("pyperclip", MagicMock())
sys.modules.setdefault("pyautogui", MagicMock())
sys.modules.setdefault("pynput", MagicMock())
sys.modules.setdefault("pynput.keyboard", MagicMock())
sys.modules.setdefault("pyaudio", MagicMock())
# faster_whisper provides WhisperModel — stub the symbol so `from faster_whisper import WhisperModel`
# resolves to a MagicMock when the real package is missing from the env running pytest.
_fw_stub = MagicMock()
_fw_stub.WhisperModel = MagicMock()
sys.modules.setdefault("faster_whisper", _fw_stub)
sys.modules.setdefault("silero_vad", MagicMock())


def _make_mock_whisper_model(text: str = "hello world", segments=None):
    """faster-whisper.transcribe returns (segments_generator, info). Mock matches that."""
    if segments is None:
        segments = [SimpleNamespace(text=text)]
    info = SimpleNamespace()
    model = MagicMock()
    model.transcribe.return_value = (iter(segments), info)
    return model


def _pcm() -> bytes:
    return (np.ones(8000, dtype=np.int16) * 1000).tobytes()


def test_lone_okay_is_kept_even_though_it_is_a_known_hallucination(caplog):
    """A one-word reply is the whole utterance; dropping it deletes a real answer."""
    import logging
    from voice_typer_whisper import WhisperTranscriber

    model = _make_mock_whisper_model(segments=[
        SimpleNamespace(text="Okay.", no_speech_prob=0.95),
    ])
    with patch("voice_typer_whisper.WhisperModel", return_value=model):
        t = WhisperTranscriber(model_name="tiny.en", device="cpu")
        assert t.wait_until_ready(timeout=5)
    with caplog.at_level(logging.INFO):
        assert t.transcribe(_pcm()) == "Okay."
    assert "Dropped likely hallucination" not in caplog.text


def test_silent_thank_you_beside_real_speech_is_dropped_and_logged(caplog):
    """The quiet gap before speech decodes as "Thank you."; the real words stay."""
    import logging
    from voice_typer_whisper import WhisperTranscriber

    model = _make_mock_whisper_model(segments=[
        SimpleNamespace(text="Thank you.", no_speech_prob=0.9),
        SimpleNamespace(text="open the file", no_speech_prob=0.05),
    ])
    with patch("voice_typer_whisper.WhisperModel", return_value=model):
        t = WhisperTranscriber(model_name="tiny.en", device="cpu")
        assert t.wait_until_ready(timeout=5)
    with caplog.at_level(logging.INFO):
        assert t.transcribe(_pcm()) == "open the file"
    assert "Dropped likely hallucination: Thank you." in caplog.text


# ---------- Change 1: frame-splitter (Silero 512 vs PyAudio 1024) ----------

def test_split_chunk_to_frames_produces_two_equal_halves():
    from voice_typer_whisper import VoiceTyperWhisper
    # 1024 samples at int16 = 2048 bytes
    data = (b"\x01\x00" * 1024)
    a, b = VoiceTyperWhisper._split_chunk_to_frames(data)
    assert len(a) == 1024 and len(b) == 1024
    # Each half is 512 int16 samples
    assert np.frombuffer(a, dtype=np.int16).size == 512
    assert np.frombuffer(b, dtype=np.int16).size == 512


# ---------- E3 / R1: load failure surfaces fast, doesn't hang 180s ----------

def test_load_failure_surfaces_via_wait_until_ready():
    from voice_typer_whisper import WhisperTranscriber

    with patch("voice_typer_whisper.WhisperModel", side_effect=OSError("HTTP 500 model download")):
        t = WhisperTranscriber(model_name="tiny.en", device="cpu")
        # Wait briefly; event must be set even though model is None
        ready = t.wait_until_ready(timeout=5)
    assert ready is False, "wait_until_ready must report False when load fails"
    assert t.load_error is not None and "500" in t.load_error
    assert t._model is None


def test_transcribe_returns_none_when_model_failed_to_load():
    from voice_typer_whisper import WhisperTranscriber

    with patch("voice_typer_whisper.WhisperModel", side_effect=OSError("no internet")):
        t = WhisperTranscriber(model_name="tiny.en", device="cpu")
        t.wait_until_ready(timeout=5)
    # Should not raise NoneType attribute error
    pcm = (np.ones(8000, dtype=np.int16) * 1000).tobytes()
    result = t.transcribe(pcm)
    assert result is None


# ---------- E1 / R7: downgrade uses _build_model helper (no whisper.load_model) ----------

def test_downgrade_swaps_model_via_build_model_helper():
    from voice_typer_whisper import WhisperTranscriber

    initial = _make_mock_whisper_model("first")
    swapped = _make_mock_whisper_model("second")

    with patch("voice_typer_whisper.WhisperModel") as mock_cls:
        mock_cls.side_effect = [initial, swapped]
        t = WhisperTranscriber(model_name="small.en", device="cuda")
        ok = t.wait_until_ready(timeout=5)
    assert ok
    assert t._model is initial

    # Normalize state regardless of any config file on the test runner.
    t._model_name = "small.en"
    t._downgrade_floor = "tiny.en"
    t._latency_samples.clear()
    t._latency_samples.extend([True] * t._downgrade_window)

    with patch("voice_typer_whisper.WhisperModel", return_value=swapped):
        t._try_downgrade()
    assert t._model is swapped
    assert t._model_name == "base.en"  # next size tier down, preserves .en suffix


# ---------- R3: Silero reset is called when an utterance ends ----------

def test_silero_reset_called_on_utterance_end():
    import voice_typer_whisper as vtw

    # Stub heavy deps so __init__ doesn't try to load real models
    with patch.object(vtw, "WhisperTranscriber") as mock_tx, \
         patch.object(vtw, "SileroVAD") as mock_vad_cls, \
         patch.object(vtw.keyboard, "Listener"), \
         patch.object(vtw, "signal"):
        mock_vad = MagicMock()
        mock_vad_cls.return_value = mock_vad
        vt = vtw.VoiceTyperWhisper()

        vt._listening_flag.set()
        vt._in_speech = True
        vt._audio_buffer = [b"\x00" * 1024] * 5
        vt._speech_frame_count = 5
        vt._silence_frame_count = vt._silence_frames_threshold - 1

        # One more silence frame → triggers end
        vt._process_vad_frame(b"\x00" * 1024, is_speech=False)

    mock_vad.reset.assert_called_once()


# ---------- R2: _type_text delegates to text_inserter for ALL text ----------

def test_type_text_delegates_to_text_inserter():
    import voice_typer_whisper as vtw

    with patch.object(vtw, "WhisperTranscriber"), \
         patch.object(vtw, "SileroVAD"), \
         patch.object(vtw.keyboard, "Listener"), \
         patch.object(vtw, "signal"):
        vt = vtw.VoiceTyperWhisper()

    fake_inserter = MagicMock()
    vt._text_inserter = fake_inserter

    vt._type_text("short")
    vt._type_text("a much longer sentence that would previously have been typed character by character")

    assert fake_inserter.insert_text.call_count == 2
    fake_inserter.insert_text.assert_any_call("short")


def test_f8_release_does_not_change_listening():
    """Alt+F8 is Cinnamon's window-resize; F8 must not also flip dictation."""
    import voice_typer_whisper as vtw

    vt = vtw.VoiceTyperWhisper.__new__(vtw.VoiceTyperWhisper)
    vt._listening_flag = threading.Event()
    vt._overlay = MagicMock()
    vt._update_status_file = MagicMock()
    vt._alt_keys = set()

    vt._on_key_release(vtw.keyboard.Key.f8)
    assert not vt._listening_flag.is_set()
    vt._overlay.set_state.assert_not_called()
    vt._update_status_file.assert_not_called()

    vt._listening_flag.set()
    vt._on_key_release(vtw.keyboard.Key.f8)
    assert vt._listening_flag.is_set()


@pytest.mark.parametrize("fallback_succeeds", [True, False])
def test_failed_text_insertion_uses_fallback_and_reports_result(fallback_succeeds):
    import voice_typer_whisper as vtw

    vt = vtw.VoiceTyperWhisper.__new__(vtw.VoiceTyperWhisper)
    vt._text_inserter = MagicMock()
    vt._text_inserter.insert_text.return_value = False
    error = None if fallback_succeeds else subprocess.CalledProcessError(1, "xdotool")

    with patch.object(vtw.subprocess, "run", side_effect=error) as run, \
         patch.object(vtw, "wait_for_modifiers_released", return_value=True):
        assert vt._type_text("dictation test") is fallback_succeeds

    run.assert_called_once_with(
        ["xdotool", "type", "--", "dictation test"],
        check=True, timeout=10,
    )


def test_xdotool_fallback_does_not_type_while_a_modifier_is_still_held():
    """Typing with Alt or Ctrl still down sprays shortcuts instead of text."""
    import voice_typer_whisper as vtw

    vt = vtw.VoiceTyperWhisper.__new__(vtw.VoiceTyperWhisper)
    vt._text_inserter = MagicMock()
    vt._text_inserter.insert_text.return_value = False

    with patch.object(vtw.subprocess, "run") as run, \
         patch.object(vtw, "wait_for_modifiers_released", return_value=False):
        assert vt._type_text("dictation test") is False

    run.assert_not_called()


def test_undo_command_never_releases_and_represses_held_keys():
    """'Clear that' sends Ctrl+Z only after modifiers are free, without
    --clearmodifiers (which can leave Super/Alt stuck and cut off push-to-talk)."""
    import voice_typer_whisper as vtw

    vt = vtw.VoiceTyperWhisper.__new__(vtw.VoiceTyperWhisper)
    vt._last_typed_text = "hello "
    vt._history = None
    vt._overlay = None
    vt._play_cmd_ack = MagicMock()
    order = []
    with patch.object(vtw, "wait_for_modifiers_released",
                      side_effect=lambda *a, **k: order.append("wait") or True), \
         patch.object(vtw.subprocess, "run", side_effect=lambda argv, **k: order.append(argv)):
        vt._handle_clear_last()

    assert order == ["wait", ["xdotool", "key", "ctrl+z"]]


def _transcribe_stub():
    import voice_typer_whisper as vtw

    vt = vtw.VoiceTyperWhisper.__new__(vtw.VoiceTyperWhisper)
    vt._transcribe_lock = threading.Lock()
    vt._warn_mic_silent = MagicMock()
    return vtw, vt


def test_push_to_talk_waits_for_the_previous_utterance_instead_of_dropping_it():
    vtw, vt = _transcribe_stub()
    vt._transcribe_lock.acquire()  # the previous utterance is still being typed
    with patch.object(vtw, "is_silent_capture", return_value=True):
        worker = threading.Thread(target=vt._transcribe_and_type, args=(b"\0" * 64,),
                                  kwargs={"is_ptt": True})
        worker.start()
        time.sleep(0.3)
        assert worker.is_alive(), "push-to-talk utterance was dropped instead of queued"
        vt._transcribe_lock.release()
        worker.join(timeout=2)

    assert not worker.is_alive()
    vt._warn_mic_silent.assert_called_once()  # it went on to process the audio


def test_continuous_dictation_still_drops_an_overlapping_segment():
    vtw, vt = _transcribe_stub()
    vt._transcribe_lock.acquire()
    with patch.object(vtw, "is_silent_capture", return_value=True):
        vt._transcribe_and_type(b"\0" * 64, is_ptt=False)  # returns at once
    vt._warn_mic_silent.assert_not_called()
    vt._transcribe_lock.release()


def test_toggle_records_which_switch_fired(caplog):
    import signal as _signal
    import voice_typer_whisper as vtw

    vt = vtw.VoiceTyperWhisper.__new__(vtw.VoiceTyperWhisper)
    vt._listening_flag = threading.Event()
    vt._overlay = None
    vt._update_status_file = MagicMock()
    with caplog.at_level("INFO"):
        vt._handle_toggle_signal(None, None)
        vt._handle_toggle_signal(_signal.SIGUSR1, None)

    assert "Listening RESUMED (via tray icon or voice command)" in caplog.text
    assert "Listening PAUSED (via SIGUSR1 (tray icon or control script))" in caplog.text
