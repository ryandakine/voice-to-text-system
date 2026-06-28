"""Regression tests for the silent-capture guard.

Intent: when the mic is muted (CMTECK physical mute button) or the default input
drifted to a dead device, a sustained push-to-talk press captures near-silence.
The app must NOT type Whisper's "You"/"Thank you." hallucination on that silence.
`is_silent_capture` is the gate; these tests pin the exact behavior that catches a
muted mic while never suppressing real (even quiet) speech or short accidental taps.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from voice_typer_whisper import (
    SAMPLE_RATE,
    SILENCE_RMS_THRESHOLD,
    is_silent_capture,
)


def _pcm(samples: np.ndarray) -> bytes:
    return samples.astype(np.int16).tobytes()


def test_long_silent_capture_is_flagged() -> None:
    # 2s of pure silence = muted/dead mic (measured RMS 0 on the real muted CMTECK).
    silent = _pcm(np.zeros(2 * SAMPLE_RATE))
    assert is_silent_capture(silent) is True


def test_normal_speech_not_flagged() -> None:
    # 2s of strong signal (RMS ~2100) = real speech -> must transcribe normally.
    t = np.linspace(0, 2, 2 * SAMPLE_RATE, endpoint=False)
    speech = _pcm(3000 * np.sin(2 * np.pi * 180 * t))
    assert is_silent_capture(speech) is False


def test_quiet_unmuted_ambient_not_flagged() -> None:
    # Unmuted CMTECK ambient measured ~673 RMS; well above threshold -> not flagged.
    rng = np.random.default_rng(0)
    ambient = _pcm(rng.normal(0, 600, 2 * SAMPLE_RATE))
    assert is_silent_capture(ambient) is False
    assert 600 > SILENCE_RMS_THRESHOLD  # sanity: the gap is real, not threshold luck


def test_short_silent_tap_ignored() -> None:
    # 0.3s of silence = accidental Alt tap, too short to judge -> not flagged.
    tap = _pcm(np.zeros(int(0.3 * SAMPLE_RATE)))
    assert is_silent_capture(tap) is False


def test_empty_capture_not_flagged() -> None:
    assert is_silent_capture(b"") is False


def test_odd_length_dummy_bytes_do_not_crash() -> None:
    # Regression: short odd-length buffers (e.g. b"fakeaudio", as the voice-command
    # integration tests pass) must not raise on np.frombuffer(int16) — and are too
    # short to judge, so the transcribe path proceeds normally.
    assert is_silent_capture(b"fakeaudio") is False
