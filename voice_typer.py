#!/usr/bin/env python3
"""IBM Granite 4.0 1B Speech powered voice-to-text typer.

Fully local, offline, no API key required.

Features
--------
- Records microphone audio locally (16 kHz mono, linear16).
- Uses RMS-based VAD to detect speech start/end.
- On utterance end, transcribes with IBM Granite 4.0 1B Speech locally.
- Types transcript into focused window via xdotool.
- F8 hotkey toggles always-listening mode.
- Alt (Left or Right) = Push-to-Talk.
- Starts in PAUSED mode by default.
- SIGUSR1 toggles listening. SIGUSR2 toggles PTT. SIGRTMIN toggles OpenClaw.

Usage
-----
1. Install deps:
   pip install -r requirements.txt

2. Run:
   python voice_typer.py

3. Press F8 to start listening, speak, and text appears in your focused window.
   Hold Alt for Push-to-Talk. Ctrl+C to exit.

Model: ibm-granite/granite-4.0-1b-speech (~2 GB download on first run, cached after)
"""

import json
import logging
import os
import sys
import threading
import time
from typing import Optional

import numpy as np
import pyaudio
import psutil
import signal
import atexit
from pynput import keyboard


# ---------------------------------------------------------------------------
# Audio settings
# ---------------------------------------------------------------------------
SAMPLE_RATE = 16000
CHANNELS = 1
FORMAT = pyaudio.paInt16
CHUNK_SIZE = 1024  # ~64 ms per chunk at 16 kHz

# VAD thresholds (RMS of int16 audio, range 0–32768)
SPEECH_THRESHOLD = 500   # RMS above this → speech detected
SILENCE_THRESHOLD = 300  # RMS below this → silence
SILENCE_CHUNKS = 7       # ~448 ms of silence → utterance ended
MIN_SPEECH_CHUNKS = 3    # skip if fewer than ~192 ms of speech
MAX_BUFFER_CHUNKS = int(30 * SAMPLE_RATE / CHUNK_SIZE)  # 30-second hard cap


# ---------------------------------------------------------------------------
# Granite transcriber
# ---------------------------------------------------------------------------

class GraniteTranscriber:
    """Loads IBM Granite 4.0 1B Speech and transcribes raw PCM audio."""

    MODEL_ID = "ibm-granite/granite-4.0-1b-speech"

    def __init__(self):
        self._model = None
        self._processor = None
        self._tokenizer = None
        self._device = None
        self._lock = threading.Lock()
        self._loaded = threading.Event()
        threading.Thread(target=self._load, daemon=True, name="granite-loader").start()

    def _load(self):
        try:
            import torch
            from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor

            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            logging.info(
                "Loading Granite 4.0 1B Speech on %s "
                "(first run downloads ~2 GB, cached after)...",
                self._device,
            )

            self._processor = AutoProcessor.from_pretrained(self.MODEL_ID)
            self._tokenizer = self._processor.tokenizer
            self._model = AutoModelForSpeechSeq2Seq.from_pretrained(
                self.MODEL_ID,
                device_map=self._device,
                torch_dtype=torch.bfloat16,
            )
            self._model.eval()

            # Compile model for faster repeated inference (PyTorch 2.x)
            try:
                self._model = torch.compile(self._model, mode="reduce-overhead")
                logging.info("torch.compile applied.")
            except Exception:
                pass  # compile is optional, not available on all setups

            # Pre-warm: run one dummy inference so the first real transcription is fast
            self._prewarm(torch)

            self._loaded.set()
            logging.info("Granite 4.0 model ready.")

        except Exception as exc:
            logging.error("Failed to load Granite model: %s", exc)

    def _prewarm(self, torch):
        """Run a silent dummy inference to warm up the GPU/CUDA kernels."""
        try:
            dummy_audio = torch.zeros(1, SAMPLE_RATE, dtype=torch.float32)  # 1s silence
            chat = [{"role": "user", "content": "<|audio|>can you transcribe the speech?"}]
            prompt = self._tokenizer.apply_chat_template(chat, tokenize=False, add_generation_prompt=True)
            inputs = self._processor(prompt, dummy_audio, device=self._device, return_tensors="pt").to(self._device)
            with torch.no_grad():
                self._model.generate(**inputs, max_new_tokens=5)
            logging.info("Model pre-warmed.")
        except Exception as exc:
            logging.warning("Pre-warm failed (non-fatal): %s", exc)

    def wait_until_ready(self, timeout: float = 180) -> bool:
        return self._loaded.wait(timeout=timeout)

    def transcribe(self, audio_bytes: bytes) -> Optional[str]:
        """Transcribe raw int16 PCM bytes captured at 16 kHz mono."""
        if not self._loaded.is_set():
            logging.warning("Granite model not ready, dropping utterance.")
            return None

        import torch

        # int16 PCM → float32 normalized to [-1, 1]
        audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        if audio_np.size == 0:
            return None

        # Shape expected by processor: [channels, samples]
        wav = torch.tensor(audio_np).unsqueeze(0)

        chat = [{"role": "user", "content": "<|audio|>can you transcribe the speech?"}]
        prompt = self._tokenizer.apply_chat_template(
            chat, tokenize=False, add_generation_prompt=True
        )

        try:
            with self._lock:
                inputs = self._processor(
                    prompt, wav, device=self._device, return_tensors="pt"
                ).to(self._device)

                with torch.no_grad():
                    outputs = self._model.generate(**inputs, max_new_tokens=200)

                n = inputs["input_ids"].shape[-1]
                decoded = self._tokenizer.batch_decode(
                    outputs[0, n:].unsqueeze(0), skip_special_tokens=True
                )

            text = decoded[0].strip() if decoded else ""
            return text if text else None

        except Exception as exc:
            logging.error("Transcription error: %s", exc)
            return None


# ---------------------------------------------------------------------------
# Microphone streamer (fills a queue with raw PCM chunks)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Main VoiceTyper
# ---------------------------------------------------------------------------

class VoiceTyper:
    """Manages mic capture, VAD, Granite transcription, and keystroke typing."""

    def __init__(self):
        self._transcriber = GraniteTranscriber()

        self._stop_event = threading.Event()
        self._listening_flag = threading.Event()  # F8 toggle (starts OFF)
        self._ptt_active = False
        self._openclaw_mode = False
        self._openclaw_speaking = False

        # VAD state
        self._audio_buffer: list[bytes] = []
        self._speech_chunks = 0
        self._silence_chunks = 0
        self._in_speech = False
        self._buffer_lock = threading.Lock()

        # PTT buffer (separate from VAD buffer)
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
        signal.signal(signal.SIGRTMIN, self._handle_openclaw_toggle_signal)

        self._update_status_file()

    # ------------------------------------------------------------------
    # Audio chunk callback (called from mic thread for every chunk)
    # ------------------------------------------------------------------

    def _on_audio_chunk(self, data: bytes):
        """Route each mic chunk to PTT buffer or VAD state machine."""
        if self._ptt_active:
            with self._ptt_lock:
                self._ptt_buffer.append(data)
            return

        if not self._listening_flag.is_set():
            return

        # Don't capture audio while OpenClaw is speaking (avoid echo)
        if self._openclaw_speaking:
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

    # ------------------------------------------------------------------
    # Transcription + typing
    # ------------------------------------------------------------------

    def _transcribe_and_type(self, audio_bytes: bytes):
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

        if self._openclaw_mode:
            logging.info("OpenClaw: %s", text)
            threading.Thread(
                target=self._handle_openclaw_query, args=(text,), daemon=True
            ).start()
        else:
            logging.info("Typing: %s", text)
            self._type_text(text + " ")

    # ------------------------------------------------------------------
    # Keyboard listener
    # ------------------------------------------------------------------

    def _on_key_press(self, key):
        if key in self._alt_keys and not self._alt_pressed:
            self._alt_pressed = True
            self._ptt_active = True
            with self._ptt_lock:
                self._ptt_buffer = []
            logging.info("Alt key pressed — PTT ACTIVE")
            return False  # suppress Alt to prevent focus shift

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
            return False  # suppress Alt

    # ------------------------------------------------------------------
    # Typing
    # ------------------------------------------------------------------

    def _type_text(self, text: str):
        if not text:
            return
        try:
            import subprocess
            subprocess.run(
                ["xdotool", "type", "--clearmodifiers", "--", text],
                check=True,
                timeout=10,
            )
        except Exception as exc:
            logging.error("xdotool failed: %s", exc)

    # ------------------------------------------------------------------
    # OpenClaw AI mode
    # ------------------------------------------------------------------

    def _handle_openclaw_query(self, user_text: str):
        import subprocess

        try:
            result = subprocess.run(
                ["openclaw", "task", "--no-stream", "--quiet", user_text],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=os.path.expanduser("~"),
            )
            reply = result.stdout.strip() or "No response from OpenClaw."
            logging.info("OpenClaw reply: %s", reply[:200])

            self._openclaw_speaking = True
            try:
                self._speak_response(reply)
            finally:
                time.sleep(0.3)
                self._openclaw_speaking = False

        except subprocess.TimeoutExpired:
            logging.error("OpenClaw timeout")
        except Exception as exc:
            logging.error("OpenClaw error: %s", exc)

    def _speak_response(self, text: str):
        """Speak text using Deepgram TTS (still used for OpenClaw responses)."""
        import subprocess
        import tempfile
        import urllib.request
        from dotenv import load_dotenv

        load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
        api_key = os.getenv("DEEPGRAM_API_KEY", "")
        if not api_key:
            return

        try:
            url = "https://api.deepgram.com/v1/speak?model=aura-asteria-en"
            data = json.dumps({"text": text}).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Authorization": f"Token {api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                audio = resp.read()

            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(audio)
                tmp = f.name

            subprocess.run(["mpv", "--no-video", "--really-quiet", tmp], timeout=30)
            os.unlink(tmp)

        except Exception as exc:
            logging.error("TTS error: %s", exc)

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

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

    def _handle_openclaw_toggle_signal(self, signum, frame):
        self._openclaw_mode = not self._openclaw_mode
        logging.info("OpenClaw mode %s", "ENABLED" if self._openclaw_mode else "DISABLED")

    def _update_status_file(self):
        state = "ON" if self._listening_flag.is_set() else "OFF"
        try:
            with open("/tmp/voice_typer_status", "w") as f:
                f.write(state)
        except Exception as exc:
            logging.warning("Failed to write status file: %s", exc)

    # ------------------------------------------------------------------
    # Run / stop
    # ------------------------------------------------------------------

    def run(self):
        logging.info("Starting VoiceTyper with Granite 4.0 1B Speech (local, no API key)")
        logging.info("Waiting for model to load...")

        if not self._transcriber.wait_until_ready(timeout=180):
            logging.error("Model failed to load within 3 minutes. Exiting.")
            sys.exit(1)

        logging.info("Model ready. Press F8 to toggle listening. Hold Alt for PTT. Ctrl+C to exit.")

        self._mic.start()
        self._keyboard_listener.start()

        try:
            while not self._stop_event.is_set():
                time.sleep(0.1)
        except KeyboardInterrupt:
            logging.info("Shutting down...")
        finally:
            self.stop()

    def stop(self):
        self._stop_event.set()
        self._mic.stop()


# ---------------------------------------------------------------------------
# Singleton enforcement
# ---------------------------------------------------------------------------

def enforce_singleton():
    lock_file = "/tmp/voice_typer.pid"

    if os.path.exists(lock_file):
        try:
            with open(lock_file) as f:
                old_pid = int(f.read().strip())
            if psutil.pid_exists(old_pid):
                logging.warning("Found old instance (PID %d), terminating...", old_pid)
                try:
                    p = psutil.Process(old_pid)
                    p.terminate()
                    p.wait(timeout=3)
                except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                    if psutil.pid_exists(old_pid):
                        os.kill(old_pid, signal.SIGKILL)
                logging.info("Old instance terminated.")
        except Exception as exc:
            logging.warning("Lock file check failed: %s", exc)

    try:
        with open(lock_file, "w") as f:
            f.write(str(os.getpid()))

        def _remove_lock():
            try:
                os.remove(lock_file)
            except FileNotFoundError:
                pass

        atexit.register(_remove_lock)
    except Exception as exc:
        logging.error("Failed to write lock file: %s", exc)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    for noisy in ["transformers", "urllib3", "asyncio"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)

    enforce_singleton()
    VoiceTyper().run()


if __name__ == "__main__":
    main()
