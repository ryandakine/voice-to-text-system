#!/usr/bin/env python3
"""Voice typer using local Whisper STT with Adreno-style VAD.

Provider: "whisper" in ~/.voice_typer/provider.txt
Hotkeys: F8 toggle on/off, Alt push-to-talk
No network calls. Model runs locally on GPU or CPU.
"""

import json
import logging
import os
import signal
import subprocess
import tempfile
import threading
import time
from typing import Optional

import numpy as np
import pyaudio
from pynput import keyboard

import whisper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

# Audio settings (identical to voice_typer.py)
SAMPLE_RATE = 16000
CHANNELS = 1
FORMAT = pyaudio.paInt16
CHUNK_SIZE = 1024

# VAD thresholds (matched to Granite voice_typer.py, Codex fix #2)
SPEECH_THRESHOLD = 500
SILENCE_THRESHOLD = 300
SILENCE_CHUNKS = 7
MIN_SPEECH_CHUNKS = 3
MAX_BUFFER_CHUNKS = int(30 * SAMPLE_RATE / CHUNK_SIZE)


class WhisperTranscriber:
    """Loads Whisper model and transcribes raw PCM audio. Blocks until ready."""

    def __init__(self, model_name: str = "small", device: str = "cuda"):
        self._model = None
        self._model_name = model_name
        self._device = device
        self._loaded = threading.Event()
        self._lock = threading.Lock()

        # Read config
        config_path = os.path.expanduser("~/.config/voice-to-text/config.ini")
        if os.path.exists(config_path):
            import configparser
            cfg = configparser.ConfigParser()
            cfg.read(config_path)
            if cfg.has_section("Whisper"):
                self._model_name = cfg.get("Whisper", "model", fallback=model_name)
                self._device = cfg.get("Whisper", "device", fallback=device)
                self._language = cfg.get("Whisper", "language", fallback="en")
                self._fp16 = cfg.getboolean("Whisper", "fp16", fallback=True)
                self._temperature = cfg.getfloat("Whisper", "temperature", fallback=0.0)
            else:
                self._language = "en"
                self._fp16 = True
                self._temperature = 0.0
        else:
            self._language = "en"
            self._fp16 = True
            self._temperature = 0.0

        # Load in background thread
        threading.Thread(target=self._load, daemon=True, name="whisper-loader").start()

    def _load(self):
        try:
            logging.info("Loading Whisper model '%s' on %s...", self._model_name, self._device)
            cache_dir = os.path.expanduser("~/.cache/whisper")
            self._model = whisper.load_model(
                self._model_name,
                device=self._device,
                download_root=cache_dir,
            )
            self._loaded.set()
            logging.info("Whisper model loaded.")
        except Exception as exc:
            logging.error("Failed to load Whisper model: %s", exc)

    def wait_until_ready(self, timeout: float = 180) -> bool:
        return self._loaded.wait(timeout=timeout)

    def transcribe(self, audio_bytes: bytes) -> Optional[str]:
        """Transcribe raw int16 PCM bytes at 16 kHz mono."""
        if not self._loaded.is_set():
            logging.warning("Whisper model not ready, dropping utterance.")
            return None

        audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        if audio_np.size == 0:
            return None

        # Codex fix #4: preserve language auto-detection
        lang = self._language if self._language != "auto" else None

        try:
            with self._lock:
                result = self._model.transcribe(
                    audio_np,
                    language=lang,
                    task="transcribe",
                    temperature=self._temperature,
                    fp16=self._fp16,
                )
            text = result.get("text", "").strip()
            return text if text else None
        except Exception as exc:
            logging.error("Whisper transcription error: %s", exc)
            # Codex fix #1 (eng review): fallback to temp file
            try:
                import soundfile as sf
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    sf.write(f.name, audio_np, SAMPLE_RATE)
                    tmp = f.name
                with self._lock:
                    result = self._model.transcribe(tmp, language=lang, fp16=self._fp16)
                os.unlink(tmp)
                text = result.get("text", "").strip()
                return text if text else None
            except Exception as exc2:
                logging.error("Whisper fallback also failed: %s", exc2)
                return None


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
    """Manages mic capture, VAD, Whisper transcription, and keystroke typing."""

    def __init__(self):
        self._transcriber = WhisperTranscriber()

        self._stop_event = threading.Event()
        self._listening_flag = threading.Event()
        self._ptt_active = False

        # Codex fix #8: serialize transcription (one at a time)
        self._transcribe_lock = threading.Lock()

        # VAD state
        self._audio_buffer: list[bytes] = []
        self._speech_chunks = 0
        self._silence_chunks = 0
        self._in_speech = False
        self._buffer_lock = threading.Lock()

        # PTT buffer
        self._ptt_buffer: list[bytes] = []
        self._ptt_lock = threading.Lock()

        # Dedup
        self._last_transcript = ""
        self._last_transcript_time = 0.0
        self._typing_lock = threading.Lock()

        # Mic
        self._mic = MicrophoneStreamer(self._on_audio_chunk, self._stop_event)

        # Keyboard
        self._alt_keys = {keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt}
        self._alt_pressed = False
        self._keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release,
        )

        # Signals
        signal.signal(signal.SIGUSR1, self._handle_toggle_signal)
        signal.signal(signal.SIGUSR2, self._handle_ptt_signal)

        self._update_status_file()

    def _on_audio_chunk(self, data: bytes):
        if self._ptt_active:
            with self._ptt_lock:
                self._ptt_buffer.append(data)
            return

        if not self._listening_flag.is_set():
            return

        rms = self._rms(data)

        with self._buffer_lock:
            if not self._in_speech:
                if rms >= SPEECH_THRESHOLD:
                    self._in_speech = True
                    self._audio_buffer = [data]
                    self._speech_chunks = 1
                    self._silence_chunks = 0
                    logging.debug("VAD: speech started (rms=%.0f)", rms)
            else:
                self._audio_buffer.append(data)
                self._speech_chunks += 1

                if rms < SILENCE_THRESHOLD:
                    self._silence_chunks += 1
                else:
                    self._silence_chunks = 0

                utterance_ended = self._silence_chunks >= SILENCE_CHUNKS
                buffer_full = len(self._audio_buffer) >= MAX_BUFFER_CHUNKS

                if utterance_ended or buffer_full:
                    if self._speech_chunks >= MIN_SPEECH_CHUNKS:
                        audio_bytes = b"".join(self._audio_buffer)
                        threading.Thread(
                            target=self._transcribe_and_type,
                            args=(audio_bytes,),
                            daemon=True,
                        ).start()
                    self._audio_buffer = []
                    self._speech_chunks = 0
                    self._silence_chunks = 0
                    self._in_speech = False

    @staticmethod
    def _rms(data: bytes) -> float:
        audio = np.frombuffer(data, dtype=np.int16).astype(np.float32)
        return float(np.sqrt(np.mean(audio ** 2))) if audio.size else 0.0

    def _transcribe_and_type(self, audio_bytes: bytes):
        # Codex fix #8: serialize, don't stack parallel transcriptions
        if not self._transcribe_lock.acquire(blocking=False):
            logging.debug("Transcription in progress, dropping utterance.")
            return
        try:
            text = self._transcriber.transcribe(audio_bytes)
            if not text:
                return

            now = time.time()
            with self._typing_lock:
                if (
                    text.lower() == self._last_transcript.lower()
                    and now - self._last_transcript_time < 3.0
                ):
                    logging.debug("Duplicate ignored: %s", text)
                    return
                self._last_transcript = text
                self._last_transcript_time = now

            logging.info("Typing: %s", text)
            self._type_text(text + " ")
        finally:
            self._transcribe_lock.release()

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
        if not text:
            return
        try:
            subprocess.run(
                ["xdotool", "type", "--clearmodifiers", "--", text],
                check=True,
                timeout=10,
            )
        except Exception as exc:
            logging.error("xdotool failed: %s", exc)

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
        # Codex fix #5/#7: block on model load (same as Granite), no OpenClaw mode
        logging.info("Starting VoiceTyper with Whisper (local, no API key)")
        logging.info("Waiting for Whisper model to load...")

        if not self._transcriber.wait_until_ready(timeout=180):
            logging.error("Whisper model failed to load within 3 minutes. Exiting.")
            return

        logging.info("Model ready. F8 to toggle, Alt to push-to-talk.")
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
        logging.info("VoiceTyperWhisper stopped.")


if __name__ == "__main__":
    VoiceTyperWhisper().run()
