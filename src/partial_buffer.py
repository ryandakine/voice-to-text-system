"""Streaming partial transcription for voice_typer_whisper (Change 3).

Per the round-2 plan review, partials are displayed in the overlay ONLY.
They do not type into the target window. This sidesteps:
- O(n²) compute blow-up (we cap the transcribe window)
- Wrong-window contamination on focus change
- Clipboard-vs-keystroke confusion

Algorithm:
- Background timer fires every `interval_ms` while Silero VAD reports
  in_speech.
- On each tick, snapshot the last `max_window_ms` of audio (bounded,
  so cost is constant regardless of utterance length).
- Transcribe the snapshot via the existing faster-whisper model.
- Apply hysteresis (min_diff_chars) — only emit to overlay if the text
  changed by more than N characters from the previous partial.
- When the utterance ends, stop emitting partials. The main pipeline
  runs a full-utterance transcribe as usual and routes that final text
  to the target window via text_inserter.
"""

import logging
import threading
import time
from typing import Callable, Optional

import numpy as np


SAMPLE_RATE = 16000
CHUNK_SIZE = 1024  # PyAudio read size in samples
SAMPLE_BYTES = 2   # int16 mono


class PartialBuffer:
    """Emits interim transcripts from a growing audio buffer at a fixed cadence.

    Parameters
    ----------
    transcribe_fn
        Callable that takes raw int16 PCM bytes at 16kHz mono and returns
        Optional[str]. Typically WhisperTranscriber.transcribe bound method.
    on_partial
        Callable(text: str) invoked with each committed partial.
    interval_ms
        How often to emit a partial while speaking.
    max_window_ms
        Bounded snapshot window. 5000 ms means each tick transcribes at
        most 5 seconds of audio regardless of utterance length.
    min_diff_chars
        Hysteresis — skip emission if new partial differs from previous
        by fewer than this many characters.
    """

    def __init__(
        self,
        transcribe_fn: Callable[[bytes], Optional[str]],
        on_partial: Callable[[str], None],
        interval_ms: int = 1200,
        max_window_ms: int = 5000,
        min_diff_chars: int = 2,
    ):
        self._transcribe = transcribe_fn
        self._on_partial = on_partial
        self._interval = max(0.3, interval_ms / 1000.0)
        self._max_window_bytes = int((max_window_ms / 1000.0) * SAMPLE_RATE) * SAMPLE_BYTES
        self._min_diff = max(0, min_diff_chars)

        self._lock = threading.Lock()
        self._frames: list = []
        self._in_speech = False
        self._last_partial = ""
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ---------- lifecycle ----------

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="partial-buffer"
        )
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None

    # ---------- audio ingestion ----------

    def on_utterance_start(self):
        with self._lock:
            self._frames = []
            self._last_partial = ""
            self._in_speech = True

    def append_frame(self, raw: bytes):
        """Called per audio chunk (from the VAD callback thread)."""
        if not raw:
            return
        with self._lock:
            if not self._in_speech:
                return
            self._frames.append(raw)
            # Cap retained bytes to the window so this never grows unbounded.
            total = sum(len(f) for f in self._frames)
            while total > self._max_window_bytes and self._frames:
                total -= len(self._frames[0])
                self._frames.pop(0)

    def on_utterance_end(self):
        with self._lock:
            self._in_speech = False
            self._frames = []
            last = self._last_partial
            self._last_partial = ""
        # Clear overlay partial on utterance end — main pipeline will take over
        if last:
            try:
                self._on_partial("")
            except Exception:
                pass

    # ---------- internal ----------

    def _snapshot(self) -> Optional[bytes]:
        with self._lock:
            if not self._in_speech or not self._frames:
                return None
            return b"".join(self._frames)

    def _run(self):
        while not self._stop_event.is_set():
            t0 = time.monotonic()
            audio = self._snapshot()
            if audio is not None and len(audio) >= SAMPLE_BYTES * SAMPLE_RATE // 4:
                # Have at least 250ms of audio → try a partial
                try:
                    text = self._transcribe(audio)
                except Exception as exc:
                    logging.debug("partial transcribe failed: %s", exc)
                    text = None
                if text:
                    with self._lock:
                        should_emit = abs(len(text) - len(self._last_partial)) >= self._min_diff
                        if should_emit:
                            self._last_partial = text
                    if should_emit:
                        try:
                            self._on_partial(text)
                        except Exception as exc:
                            logging.debug("on_partial callback error: %s", exc)

            elapsed = time.monotonic() - t0
            sleep_for = max(0.05, self._interval - elapsed)
            # Chunked sleep so stop() is responsive
            end = time.monotonic() + sleep_for
            while time.monotonic() < end and not self._stop_event.is_set():
                time.sleep(min(0.1, end - time.monotonic()))
