#!/usr/bin/env python3
"""Voice typer using local faster-whisper (CTranslate2) STT + Silero VAD.

Provider: "whisper" in ~/.voice_typer/provider.txt
Hotkeys: F8 toggle on/off, Alt push-to-talk
Model runs locally on GPU or CPU via CTranslate2.
"""

import logging
import math
import os
import signal
import subprocess
import threading
import time
from collections import deque
from typing import Optional

import numpy as np
import pyaudio
from pynput import keyboard

from faster_whisper import WhisperModel

from voice_commands import VoiceCommandProcessor, VoiceCommand

# Optional overlay — lazy-imported so tests and CI without GTK still work.
try:
    from src.listening_overlay import ListeningOverlay, OverlayState
    OVERLAY_AVAILABLE = True
except Exception:
    OVERLAY_AVAILABLE = False
    class OverlayState:  # type: ignore
        OFF = "off"
        LOADING = "loading"
        IDLE = "idle"
        SPEECH = "speech"
        TRANSCRIBING = "transcribing"
        ERROR = "error"

_MODEL_TIERS = ["large-v3", "large-v2", "large", "medium", "small", "base", "tiny"]
# Full chain for bookkeeping/discovery; the actual step function uses _MODEL_TIERS
# so `small.en` → `base.en` (next real size tier), not `small.en` → `small`.
DOWNGRADE_CHAIN = list(_MODEL_TIERS)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

SAMPLE_RATE = 16000
CHANNELS = 1
FORMAT = pyaudio.paInt16
CHUNK_SIZE = 1024                        # PyAudio read size in samples
SILERO_FRAME_SAMPLES = 512               # Silero requires exactly 512 samples at 16kHz
FRAME_MS = SILERO_FRAME_SAMPLES * 1000 / SAMPLE_RATE  # 32.0 ms per Silero frame


class SileroVAD:
    """Thread-safe wrapper around Silero neural VAD. Warm-up on load."""

    def __init__(self, threshold: float = 0.5):
        self._threshold = threshold
        self._model = None
        self._torch = None
        self._lock = threading.Lock()
        self._loaded = threading.Event()
        self.load_error: Optional[str] = None
        threading.Thread(target=self._load, daemon=True, name="silero-loader").start()

    def _load(self) -> None:
        try:
            logging.info("Loading Silero VAD...")
            import torch
            from silero_vad import load_silero_vad
            self._torch = torch
            model = load_silero_vad()
            with torch.no_grad():
                model(torch.zeros(SILERO_FRAME_SAMPLES), SAMPLE_RATE)
            self._model = model
            logging.info("Silero VAD loaded.")
        except Exception as exc:
            self.load_error = str(exc)
            self._model = None
            logging.error("Silero VAD load failed: %s", exc)
        finally:
            self._loaded.set()

    def wait_until_ready(self, timeout: float = 60) -> bool:
        self._loaded.wait(timeout=timeout)
        return self._model is not None

    def is_speech(self, frame_float32: np.ndarray) -> bool:
        """frame_float32: 512 samples, float32, range [-1, 1]. Fails open on error."""
        if self._model is None:
            return True
        try:
            with self._lock:
                with self._torch.no_grad():
                    prob = self._model(
                        self._torch.from_numpy(frame_float32), SAMPLE_RATE
                    ).item()
            self._last_prob = prob
            return prob >= self._threshold
        except Exception as exc:
            logging.debug("Silero inference error: %s", exc)
            return True

    @property
    def last_prob(self) -> float:
        return getattr(self, "_last_prob", 0.0)

    def reset(self) -> None:
        """Reset GRU state between utterances. Must run under silero lock (R3)."""
        if self._model is None:
            return
        with self._lock:
            try:
                self._model.reset_states()
            except Exception:
                pass


class WhisperTranscriber:
    """Loads faster-whisper model and transcribes raw PCM audio."""

    def __init__(self, model_name: str = "small.en", device: str = "cuda"):
        self._model: Optional[WhisperModel] = None
        self._model_name = model_name
        self._device = device
        self._loaded = threading.Event()
        self.load_error: Optional[str] = None

        self._lock = threading.Lock()              # swap + inference serialization
        self._downgrade_lock = threading.Lock()    # prevent concurrent downgrades (R7)

        self._auto_downgrade = True
        self._downgrade_rtf = 0.3
        self._downgrade_abs_s = 1.2
        self._downgrade_window = 5
        self._downgrade_trigger = 3
        self._downgrade_floor = "tiny.en"

        self._language = "en"
        self._temperature = 0.0

        config_path = os.path.expanduser("~/.config/voice-to-text/config.ini")
        if os.path.exists(config_path):
            import configparser
            cfg = configparser.ConfigParser()
            cfg.read(config_path)
            if cfg.has_section("Whisper"):
                self._model_name = cfg.get("Whisper", "model", fallback=model_name)
                self._device = cfg.get("Whisper", "device", fallback=device)
                self._language = cfg.get("Whisper", "language", fallback="en")
                self._temperature = cfg.getfloat("Whisper", "temperature", fallback=0.0)
                self._auto_downgrade = cfg.getboolean("Whisper", "auto_downgrade", fallback=True)
                self._downgrade_rtf = cfg.getfloat("Whisper", "downgrade_rtf", fallback=0.3)
                self._downgrade_abs_s = cfg.getfloat("Whisper", "downgrade_abs_s", fallback=1.2)
                self._downgrade_window = cfg.getint("Whisper", "downgrade_window", fallback=5)
                self._downgrade_trigger = cfg.getint("Whisper", "downgrade_trigger", fallback=3)
                self._downgrade_floor = cfg.get("Whisper", "downgrade_floor", fallback="tiny.en")

        self._latency_samples: deque = deque(maxlen=self._downgrade_window)
        threading.Thread(target=self._load, daemon=True, name="whisper-loader").start()

    def _pick_compute_type(self) -> str:
        return "float16" if self._device.startswith("cuda") else "int8"

    def _build_model(self, model_name: str) -> WhisperModel:
        """Construct WhisperModel with device-aware compute_type and OOM fallback (E1, E4)."""
        cache_dir = os.path.expanduser("~/.cache/whisper")
        preferred = self._pick_compute_type()
        try:
            return WhisperModel(
                model_name,
                device=self._device,
                compute_type=preferred,
                download_root=cache_dir,
            )
        except Exception as exc:
            if self._device.startswith("cuda"):
                logging.warning(
                    "faster-whisper compute_type=%s failed (%s). Falling back to int8_float16.",
                    preferred, exc,
                )
                return WhisperModel(
                    model_name,
                    device=self._device,
                    compute_type="int8_float16",
                    download_root=cache_dir,
                )
            raise

    def _load(self) -> None:
        try:
            logging.info("Loading faster-whisper '%s' on %s...", self._model_name, self._device)
            self._model = self._build_model(self._model_name)
            effective = getattr(self._model, "compute_type", "?")
            logging.info("faster-whisper loaded (model=%s device=%s compute_type=%s)",
                         self._model_name, self._device, effective)
        except Exception as exc:
            self.load_error = str(exc)
            self._model = None
            logging.error(
                "faster-whisper load failed: %s. "
                "Check internet for first-run model download, CUDA libs, or GPU memory.",
                exc,
            )
        finally:
            self._loaded.set()

    def wait_until_ready(self, timeout: float = 180) -> bool:
        """R1: returns True ONLY if model actually loaded (not just event set)."""
        self._loaded.wait(timeout=timeout)
        return self._model is not None

    def transcribe(self, audio_bytes: bytes) -> Optional[str]:
        """Transcribe raw int16 PCM bytes at 16 kHz mono."""
        if not self._loaded.is_set():
            return None
        if self._model is None:                      # R1 guard
            return None

        audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        if audio_np.size == 0:
            return None
        audio_duration = audio_np.size / SAMPLE_RATE

        lang = self._language if self._language != "auto" else None

        t0 = time.monotonic()
        try:
            with self._lock:
                segments, _info = self._model.transcribe(
                    audio_np,
                    language=lang,
                    beam_size=1,
                    vad_filter=False,
                    condition_on_previous_text=False,
                    no_speech_threshold=0.6,
                    temperature=self._temperature,
                )
                text = " ".join(s.text for s in segments).strip()
            self._record_latency(time.monotonic() - t0, audio_duration)
            return text if text else None
        except Exception as exc:
            logging.error("faster-whisper transcription error: %s", exc)
            return None

    def _record_latency(self, elapsed: float, audio_duration: float) -> None:
        if not self._auto_downgrade or audio_duration <= 0:
            return
        rtf = elapsed / audio_duration
        is_slow = rtf > self._downgrade_rtf or elapsed > self._downgrade_abs_s
        self._latency_samples.append(is_slow)
        logging.debug("whisper latency=%.2fs audio=%.2fs rtf=%.2f slow=%s",
                      elapsed, audio_duration, rtf, is_slow)
        if (len(self._latency_samples) >= self._downgrade_window
                and sum(self._latency_samples) >= self._downgrade_trigger):
            self._try_downgrade()

    def _next_smaller_model(self, current: str) -> Optional[str]:
        """Step to the next real size tier, preserving the .en suffix if present."""
        if current == self._downgrade_floor:
            return None
        is_en = current.endswith(".en")
        base = current[:-3] if is_en else current
        try:
            idx = _MODEL_TIERS.index(base)
        except ValueError:
            return None
        if idx + 1 >= len(_MODEL_TIERS):
            return None
        next_base = _MODEL_TIERS[idx + 1]
        nxt = f"{next_base}.en" if is_en else next_base
        # Clamp to floor
        floor = self._downgrade_floor
        floor_base = floor[:-3] if floor.endswith(".en") else floor
        try:
            floor_idx = _MODEL_TIERS.index(floor_base)
            if idx + 1 > floor_idx:
                return floor
        except ValueError:
            pass
        return nxt

    def _try_downgrade(self) -> None:
        if not self._downgrade_lock.acquire(blocking=False):
            return
        try:
            current = self._model_name
            nxt = self._next_smaller_model(current)
            if not nxt or nxt == current:
                logging.info("whisper auto-downgrade: at floor (%s), disabling.", current)
                self._auto_downgrade = False
                return
            slow_ratio = sum(self._latency_samples) / len(self._latency_samples)
            logging.warning("whisper auto-downgrade: %s → %s (%.0f%% of last %d were slow)",
                            current, nxt, slow_ratio * 100, len(self._latency_samples))
            try:
                new_model = self._build_model(nxt)
            except Exception as exc:
                logging.error("whisper auto-downgrade build failed (%s → %s): %s", current, nxt, exc)
                self._latency_samples.clear()
                return
            with self._lock:
                old = self._model
                self._model = new_model
                self._model_name = nxt
                del old
                try:
                    import torch
                    if self._device.startswith("cuda") and torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except Exception:
                    pass
            self._latency_samples.clear()
            logging.info("faster-whisper swapped to '%s'.", nxt)
            if nxt == self._downgrade_floor:
                self._auto_downgrade = False
        finally:
            self._downgrade_lock.release()


class MicrophoneStreamer:
    """Background thread that reads microphone audio and calls a callback."""

    def __init__(self, chunk_callback, stop_event: threading.Event):
        self._chunk_callback = chunk_callback
        self._stop_event = stop_event
        self._pa = None
        self._stream = None
        self._thread = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name="mic-streamer")
        self._thread.start()

    def _run(self):
        self._pa = pyaudio.PyAudio()
        try:
            self._stream = self._pa.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                input=True,
                frames_per_buffer=CHUNK_SIZE,
            )
        except Exception as exc:
            logging.error("Failed to open microphone: %s", exc)
            self._cleanup()
            return
        logging.info("Microphone stream started (rate=%d, channels=%d)", SAMPLE_RATE, CHANNELS)
        while not self._stop_event.is_set():
            try:
                data = self._stream.read(CHUNK_SIZE, exception_on_overflow=False)
            except Exception as exc:
                logging.warning("Mic read error: %s", exc)
                time.sleep(0.05)
                continue
            self._chunk_callback(data)
        self._cleanup()

    def _cleanup(self):
        try:
            if self._stream:
                self._stream.stop_stream()
                self._stream.close()
        finally:
            self._stream = None
        try:
            if self._pa:
                self._pa.terminate()
        finally:
            self._pa = None

    def stop(self):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)


class VoiceTyperWhisper:
    """Manages mic capture, Silero VAD, faster-whisper transcription, and text insertion."""

    def __init__(self):
        # VAD timing config (milliseconds, converted to 32ms-frame counts at runtime)
        vad_threshold = 0.5
        vad_silence_ms = 448        # 7 × 1024/16000 — preserves original end-of-utterance timing
        min_speech_ms = 192
        max_buffer_ms = 30000

        # Overlay config (Change 2)
        overlay_enabled = True
        overlay_position = "bottom-right"
        overlay_pulse_hz = 1.2
        audio_cues = True

        config_path = os.path.expanduser("~/.config/voice-to-text/config.ini")
        if os.path.exists(config_path):
            import configparser
            cfg = configparser.ConfigParser()
            cfg.read(config_path)
            if cfg.has_section("Whisper"):
                vad_threshold = cfg.getfloat("Whisper", "vad_threshold", fallback=vad_threshold)
                vad_silence_ms = cfg.getfloat("Whisper", "vad_silence_ms", fallback=vad_silence_ms)
                min_speech_ms = cfg.getfloat("Whisper", "min_speech_ms", fallback=min_speech_ms)
                max_buffer_ms = cfg.getfloat("Whisper", "max_buffer_ms", fallback=max_buffer_ms)
                overlay_enabled = cfg.getboolean("Whisper", "overlay_enabled", fallback=overlay_enabled)
                overlay_position = cfg.get("Whisper", "overlay_position", fallback=overlay_position)
                overlay_pulse_hz = cfg.getfloat("Whisper", "overlay_pulse_hz", fallback=overlay_pulse_hz)
                audio_cues = cfg.getboolean("Whisper", "audio_cues", fallback=audio_cues)

        self._silence_frames_threshold = max(1, math.ceil(vad_silence_ms / FRAME_MS))
        self._min_speech_frames = max(1, math.ceil(min_speech_ms / FRAME_MS))
        self._max_buffer_frames = max(10, math.ceil(max_buffer_ms / FRAME_MS))

        self._transcriber = WhisperTranscriber()
        self._vad = SileroVAD(threshold=vad_threshold)

        self._stop_event = threading.Event()
        self._listening_flag = threading.Event()
        self._listening_flag.set()  # start with continuous listening ON
        self._ptt_active = False

        self._transcribe_lock = threading.Lock()

        self._audio_buffer: list = []
        self._speech_frame_count = 0
        self._silence_frame_count = 0
        self._in_speech = False
        self._buffer_lock = threading.Lock()

        self._ptt_buffer: list = []
        self._ptt_lock = threading.Lock()

        self._last_transcript = ""
        self._last_transcript_time = 0.0
        self._last_typed_text: Optional[str] = None
        self._typing_lock = threading.Lock()

        # Lazy-cached text inserter (R7: defer import-time side effects)
        self._text_inserter = None

        # Voice command processor with wake-phrase aliases
        self._cmd = VoiceCommandProcessor(
            enabled=True,
            prefixes=["computer", "hey computer", "ok computer", "okay computer"],
        )
        self._cmd.register_handler(VoiceCommand.STOP_LISTENING, self._handle_stop_listening)
        self._cmd.register_handler(VoiceCommand.START_LISTENING, self._handle_start_listening)
        self._cmd.register_handler(VoiceCommand.CLEAR_LAST, self._handle_clear_last)
        self._cmd.register_handler(VoiceCommand.UNDO, self._handle_undo)
        self._cmd.register_handler(VoiceCommand.HELP, self._handle_help)

        # Change 2 — embedded overlay + audio cues
        self._overlay = None
        if overlay_enabled and OVERLAY_AVAILABLE:
            try:
                self._overlay = ListeningOverlay(
                    position=overlay_position,
                    pulse_hz=overlay_pulse_hz,
                    audio_cues=audio_cues,
                )
            except Exception as exc:
                logging.warning("Overlay init failed (%s), continuing headless.", exc)
                self._overlay = None

        self._mic = MicrophoneStreamer(self._on_audio_chunk, self._stop_event)

        self._alt_keys = {keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt}
        self._alt_pressed = False
        self._keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release,
        )

        signal.signal(signal.SIGUSR1, self._handle_toggle_signal)
        signal.signal(signal.SIGUSR2, self._handle_ptt_signal)

        self._update_status_file()

    @staticmethod
    def _split_chunk_to_frames(data: bytes):
        """Split 2048-byte (1024-sample) PyAudio chunk into two 1024-byte (512-sample) Silero frames."""
        half = len(data) // 2
        return (data[:half], data[half:])

    def _on_audio_chunk(self, data: bytes):
        if self._ptt_active:
            with self._ptt_lock:
                self._ptt_buffer.append(data)
            return
        if not self._listening_flag.is_set():
            return

        for raw_frame in self._split_chunk_to_frames(data):
            audio_np = np.frombuffer(raw_frame, dtype=np.int16).astype(np.float32) / 32768.0
            if audio_np.size != SILERO_FRAME_SAMPLES:
                continue
            is_speech = self._vad.is_speech(audio_np)
            self._process_vad_frame(raw_frame, is_speech)

    def _process_vad_frame(self, raw_frame: bytes, is_speech: bool):
        utterance_ended = False
        utterance_started = False
        audio_to_transcribe: Optional[bytes] = None

        with self._buffer_lock:
            if not self._in_speech:
                if is_speech:
                    self._in_speech = True
                    self._audio_buffer = [raw_frame]
                    self._speech_frame_count = 1
                    self._silence_frame_count = 0
                    utterance_started = True
            else:
                self._audio_buffer.append(raw_frame)
                self._speech_frame_count += 1
                if is_speech:
                    self._silence_frame_count = 0
                else:
                    self._silence_frame_count += 1

                ended = (self._silence_frame_count >= self._silence_frames_threshold
                         or len(self._audio_buffer) >= self._max_buffer_frames)
                if ended:
                    if self._speech_frame_count >= self._min_speech_frames:
                        audio_to_transcribe = b"".join(self._audio_buffer)
                    self._audio_buffer = []
                    self._speech_frame_count = 0
                    self._silence_frame_count = 0
                    self._in_speech = False
                    utterance_ended = True

        # Change 2: overlay state transitions
        if self._overlay is not None:
            if utterance_started:
                self._overlay.set_state(OverlayState.SPEECH)
            elif utterance_ended:
                # transcribing until final text arrives (or no audio to transcribe)
                self._overlay.set_state(
                    OverlayState.TRANSCRIBING if audio_to_transcribe else OverlayState.IDLE
                )

        # R3: reset Silero outside _buffer_lock, under _silero_lock (via vad.reset)
        if utterance_ended:
            self._vad.reset()
            if audio_to_transcribe is not None:
                threading.Thread(
                    target=self._transcribe_and_type,
                    args=(audio_to_transcribe,),
                    daemon=True,
                ).start()

    def _transcribe_and_type(self, audio_bytes: bytes):
        if not self._transcribe_lock.acquire(blocking=False):
            logging.debug("Transcription in progress, dropping utterance.")
            return
        try:
            text = self._transcriber.transcribe(audio_bytes)
            if not text:
                return

            # H2: race guard — listening may have been paused mid-transcribe
            # (e.g., by a concurrent "computer stop listening"). Honor that.
            if not self._listening_flag.is_set() and not self._ptt_active:
                logging.debug("Listening disabled after transcribe, dropping.")
                return

            # C2/C3/H3/H5 round-2 fix: voice command interception before typing
            if self._cmd.process(text) is not None:
                return

            now = time.time()
            with self._typing_lock:
                if (text.lower() == self._last_transcript.lower()
                        and now - self._last_transcript_time < 3.0):
                    return
                self._last_transcript = text
                self._last_transcript_time = now

            typed = text + " "
            logging.info("Typing: %s", text)
            self._type_text(typed)
            # Track last typed output so clear-last / undo commands know what to remove
            self._last_typed_text = typed
            # After text is inserted, return overlay to idle
            if self._overlay is not None:
                self._overlay.set_state(OverlayState.IDLE)
        finally:
            self._transcribe_lock.release()

    # ---------- Voice command handlers (Change 1) ----------

    def _play_cmd_ack(self):
        if self._overlay is not None:
            self._overlay.play_cue("cmd_ack")

    def _handle_stop_listening(self):
        self._listening_flag.clear()
        logging.info("Voice command: listening PAUSED")
        self._update_status_file()
        if self._overlay is not None:
            self._overlay.set_state(OverlayState.OFF)
        self._play_cmd_ack()

    def _handle_start_listening(self):
        self._listening_flag.set()
        logging.info("Voice command: listening RESUMED")
        self._update_status_file()
        if self._overlay is not None:
            self._overlay.set_state(OverlayState.IDLE)
        self._play_cmd_ack()

    def _handle_clear_last(self):
        """C2: use app-level undo (Ctrl+Z), not counted backspaces.
        Works regardless of clipboard-paste vs keystroke insertion."""
        try:
            subprocess.run(
                ["xdotool", "key", "--clearmodifiers", "ctrl+z"],
                check=True, timeout=5,
            )
            logging.info("Voice command: cleared last utterance via Ctrl+Z")
            self._last_typed_text = None
            self._play_cmd_ack()
        except Exception as exc:
            logging.error("clear_last failed: %s", exc)
            if self._overlay is not None:
                self._overlay.play_cue("error")

    def _handle_undo(self):
        self._handle_clear_last()

    def _handle_help(self):
        """C3: route help to notify-send, never type it into the target window."""
        help_text = self._cmd.get_help_text()
        try:
            subprocess.run(
                ["notify-send", "-t", "10000", "-i", "audio-input-microphone",
                 "Voice Typer — Commands", help_text],
                timeout=5,
            )
            logging.info("Voice command: help displayed via notify-send")
            self._play_cmd_ack()
        except Exception as exc:
            logging.error("help notify-send failed: %s", exc)

    def _on_key_press(self, key):
        if key in self._alt_keys and not self._alt_pressed:
            self._alt_pressed = True
            self._ptt_active = True
            with self._ptt_lock:
                self._ptt_buffer = []
            logging.info("Alt key pressed — PTT ACTIVE")
            return False

    def _on_key_release(self, key):
        if key in self._alt_keys and self._alt_pressed:
            self._alt_pressed = False
            self._ptt_active = False
            logging.info("Alt key released — PTT RELEASED, transcribing...")
            with self._ptt_lock:
                audio_bytes = b"".join(self._ptt_buffer)
                self._ptt_buffer = []
            if audio_bytes:
                threading.Thread(
                    target=self._transcribe_and_type,
                    args=(audio_bytes,),
                    daemon=True,
                ).start()
            return False

    def _type_text(self, text: str):
        """R2: delegate to src/text_insertion.py unconditionally (all lengths)."""
        if not text:
            return
        try:
            if self._text_inserter is None:
                from src.text_insertion import text_inserter as _ti
                self._text_inserter = _ti
            self._text_inserter.insert_text(text)
            return
        except Exception as exc:
            logging.warning("text_inserter failed (%s), falling back to xdotool.", exc)
        try:
            subprocess.run(
                ["xdotool", "type", "--clearmodifiers", "--", text],
                check=True, timeout=10,
            )
        except Exception as exc:
            logging.error("xdotool fallback failed: %s", exc)

    def _handle_toggle_signal(self, signum, frame):
        if self._listening_flag.is_set():
            self._listening_flag.clear()
            logging.info("Listening PAUSED")
        else:
            self._listening_flag.set()
            logging.info("Listening RESUMED")
        self._update_status_file()

    def _handle_ptt_signal(self, signum, frame):
        self._ptt_active = not self._ptt_active
        logging.info("PTT %s", "ACTIVE" if self._ptt_active else "RELEASED")

    def _update_status_file(self):
        state = "ON" if self._listening_flag.is_set() else "OFF"
        try:
            with open("/tmp/voice_typer_status", "w") as f:
                f.write(state)
        except Exception:
            pass

    def run(self):
        logging.info("Starting VoiceTyper with faster-whisper + Silero VAD (local)")
        logging.info("Waiting for models to load...")

        # Change 2: overlay shows "loading" while models warm up
        if self._overlay is not None:
            self._overlay.start()
            self._overlay.set_state(OverlayState.LOADING)

        if not self._transcriber.wait_until_ready(timeout=180):
            err = self._transcriber.load_error or "load timed out"
            logging.error("faster-whisper failed to load: %s. Exiting.", err)
            if self._overlay is not None:
                self._overlay.set_state(OverlayState.ERROR)
                subprocess.Popen(
                    ["notify-send", "-u", "critical", "Voice Typer",
                     f"faster-whisper failed to load: {err}"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            return

        if not self._vad.wait_until_ready(timeout=60):
            err = self._vad.load_error or "load timed out"
            logging.error("Silero VAD failed to load: %s. Exiting.", err)
            if self._overlay is not None:
                self._overlay.set_state(OverlayState.ERROR)
            return

        logging.info(
            "Ready. F8 to toggle, Alt to push-to-talk. "
            "vad_silence=%d frames (%.0f ms), min_speech=%d frames, max_buffer=%d frames.",
            self._silence_frames_threshold, self._silence_frames_threshold * FRAME_MS,
            self._min_speech_frames, self._max_buffer_frames,
        )
        if self._overlay is not None:
            self._overlay.set_state(OverlayState.IDLE)

        self._mic.start()
        self._keyboard_listener.start()

        try:
            while not self._stop_event.is_set():
                time.sleep(0.5)
        except KeyboardInterrupt:
            logging.info("Interrupted.")
        finally:
            self.stop()

    def stop(self):
        self._stop_event.set()
        self._mic.stop()
        self._keyboard_listener.stop()
        self._update_status_file()
        if self._overlay is not None:
            try:
                self._overlay.stop()
            except Exception:
                pass
        logging.info("VoiceTyperWhisper stopped.")


if __name__ == "__main__":
    VoiceTyperWhisper().run()
