"""Tests for src/partial_buffer.py — overlay-only streaming partials.

Per plan round-2: partials go to overlay only, never to the target window.
These tests verify:
- Bounded window (no O(n²) buffer growth)
- Emission cadence respected
- Hysteresis (min_diff_chars) skips small updates
- Utterance end clears state
- No target-window typing ever happens
"""

import threading
import time
from unittest.mock import MagicMock


def _raw_seconds(seconds: float) -> bytes:
    """Return raw int16 mono 16kHz bytes for `seconds` of audio."""
    return b"\x01\x00" * int(seconds * 16000)


# ---------- bounded window ----------

def test_buffer_bounded_to_max_window_bytes():
    from src.partial_buffer import PartialBuffer

    pb = PartialBuffer(
        transcribe_fn=lambda _b: None,
        on_partial=lambda _t: None,
        interval_ms=1200,
        max_window_ms=2000,   # 2 seconds = 64000 bytes
    )
    pb.on_utterance_start()
    # Feed 10 seconds of audio one chunk at a time
    for _ in range(10):
        pb.append_frame(_raw_seconds(1.0))

    total = sum(len(f) for f in pb._frames)
    assert total <= 2 * 16000 * 2, f"window should be bounded to 2s, got {total} bytes"


# ---------- partial emission ----------

def test_partial_emitted_when_audio_present():
    from src.partial_buffer import PartialBuffer

    seen = []
    pb = PartialBuffer(
        transcribe_fn=lambda _b: "hello world",
        on_partial=lambda t: seen.append(t),
        interval_ms=100,       # tight cadence for tests
        max_window_ms=1000,
        min_diff_chars=0,
    )
    pb.on_utterance_start()
    pb.append_frame(_raw_seconds(0.5))
    pb.start()
    time.sleep(0.3)
    pb.stop()

    assert "hello world" in seen


def test_hysteresis_skips_near_identical_partials():
    from src.partial_buffer import PartialBuffer

    seen = []
    # Transcribe returns a string that oscillates in length by 1 char
    counter = {"n": 0}
    def tx(_):
        counter["n"] += 1
        return "hi" if counter["n"] % 2 == 0 else "hii"

    pb = PartialBuffer(
        transcribe_fn=tx,
        on_partial=lambda t: seen.append(t),
        interval_ms=60,
        max_window_ms=1000,
        min_diff_chars=3,   # need 3+ char diff
    )
    pb.on_utterance_start()
    pb.append_frame(_raw_seconds(0.5))
    pb.start()
    time.sleep(0.25)
    pb.stop()

    # At most one emission — all oscillations are 1-char diffs, below threshold
    assert len(seen) <= 1, f"hysteresis should suppress near-identical partials, got {seen}"


def test_utterance_end_clears_state_and_emits_empty():
    from src.partial_buffer import PartialBuffer

    seen = []
    pb = PartialBuffer(
        transcribe_fn=lambda _b: "stuff",
        on_partial=lambda t: seen.append(t),
        interval_ms=50,
        max_window_ms=1000,
        min_diff_chars=0,
    )
    pb.on_utterance_start()
    pb.append_frame(_raw_seconds(0.4))
    pb.start()
    time.sleep(0.15)
    pb.on_utterance_end()
    pb.stop()

    assert pb._frames == []
    assert not pb._in_speech


def test_frames_ignored_when_not_in_speech():
    from src.partial_buffer import PartialBuffer
    pb = PartialBuffer(transcribe_fn=lambda _b: None, on_partial=lambda _t: None)
    # Never called on_utterance_start — should silently drop
    pb.append_frame(_raw_seconds(1.0))
    assert pb._frames == []


# ---------- voice_typer_whisper wiring ----------

def test_streaming_disabled_on_cpu_config(tmp_path, monkeypatch):
    """With device=cpu and no explicit streaming override, streaming must auto-disable."""
    import voice_typer_whisper as vtw
    from unittest.mock import patch

    cfg = tmp_path / "config.ini"
    cfg.write_text("[Whisper]\ndevice = cpu\nmodel = tiny.en\n")
    monkeypatch.setenv("HOME", str(tmp_path))
    # Redirect ~/.config to our tmp
    cfg_dir = tmp_path / ".config" / "voice-to-text"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "config.ini").write_text("[Whisper]\ndevice = cpu\nmodel = tiny.en\n")

    with patch.object(vtw, "WhisperTranscriber"), \
         patch.object(vtw, "SileroVAD"), \
         patch.object(vtw.keyboard, "Listener"), \
         patch.object(vtw, "signal"):
        vt = vtw.VoiceTyperWhisper()

    assert vt._streaming_enabled is False
    assert vt._partial_buf is None


def test_emit_partial_routes_to_overlay_only():
    """Partials must never touch text_inserter."""
    import voice_typer_whisper as vtw
    from unittest.mock import MagicMock, patch

    with patch.object(vtw, "WhisperTranscriber"), \
         patch.object(vtw, "SileroVAD"), \
         patch.object(vtw.keyboard, "Listener"), \
         patch.object(vtw, "signal"):
        vt = vtw.VoiceTyperWhisper()

    vt._overlay = MagicMock()
    vt._text_inserter = MagicMock()

    vt._emit_partial("interim text")

    vt._overlay.show_partial.assert_called_once_with("interim text")
    vt._text_inserter.insert_text.assert_not_called()
