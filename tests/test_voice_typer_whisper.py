"""Tests for voice_typer_whisper.py — the faster-whisper + Silero VAD path."""

import sys
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


def _make_mock_whisper_model(text: str = "hello world"):
    """faster-whisper.transcribe returns (segments_generator, info). Mock matches that."""
    segments = iter([SimpleNamespace(text=text)])
    info = SimpleNamespace()
    model = MagicMock()
    model.transcribe.return_value = (segments, info)
    return model


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
