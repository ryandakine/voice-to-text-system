#!/usr/bin/env python3
"""Simple Deepgram-powered voice-to-text "voice typer".

Features
--------
- Streams microphone audio to Deepgram Nova-2 over WebSocket using deepgram-sdk v5.x.
- Uses PyAudio for microphone capture (16 kHz mono, linear16).
- On finalized transcripts, types the text into the currently focused window via pynput.
- F8 hotkey toggles "Always Listening" mode (VAD).
- Alt (Left or Right) works as Push-to-Talk (PTT), overriding the toggle.
- Starts in PAUSED mode by default for safety.
- Reads DEEPGRAM_API_KEY from a .env file (via python-dotenv) or environment.
- Attempts to gracefully handle connection drops with automatic reconnection.

Usage
-----
1. Create a .env file next to this script with:

   DEEPGRAM_API_KEY=your_api_key_here

2. Install dependencies (from repo root):

   pip install -r requirements.txt

3. Run:

   python voice_typer.py

4. Make sure the window where you want text to appear is focused, then speak.
   Press F8 to toggle listening on/off. Ctrl+C in the terminal to exit.
"""

import json
import logging
import os
import sys
import threading
import time
from typing import Optional

import pyaudio
from dotenv import load_dotenv
import signal
import psutil
import atexit

# Load .env BEFORE importing deepgram SDK (it reads env vars at initialization)
_script_dir = os.path.dirname(os.path.abspath(__file__))
_env_path = os.path.join(_script_dir, ".env")
load_dotenv(_env_path)

from deepgram import DeepgramClient
from deepgram.core.events import EventType


# Audio settings compatible with Deepgram real-time streaming
SAMPLE_RATE = 16000
CHANNELS = 1
FORMAT = pyaudio.paInt16
CHUNK_SIZE = 1024  # frames per buffer (64ms at 16kHz) - balance of latency and stability


class MicrophoneStreamer:
    """Background thread that streams microphone audio via a callback.

    The callback is responsible for sending bytes to Deepgram.
    """

    def __init__(self, send_audio_callback, should_send_callback, stop_event: threading.Event):
        self._send_audio_callback = send_audio_callback
        self._should_send_callback = should_send_callback
        self._stop_event = stop_event

        self._pa = None
        self._stream = None
        self._thread = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        self._pa = pyaudio.PyAudio()
        try:
            self._stream = self._pa.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                input=True,
                frames_per_buffer=CHUNK_SIZE,
            )
        except Exception as exc:  # pragma: no cover - hardware dependent
            logging.error("Failed to open microphone: %s", exc)
            self._cleanup()
            return

        logging.info("Microphone stream started (rate=%d, channels=%d)", SAMPLE_RATE, CHANNELS)

        while not self._stop_event.is_set():
            try:
                data = self._stream.read(CHUNK_SIZE, exception_on_overflow=False)
            except Exception as exc:  # pragma: no cover - hardware dependent
                logging.warning("Error reading from microphone: %s", exc)
                time.sleep(0.1)
                continue

            # Only send audio when listening is enabled (Toggle ON or PTT held)
            if self._should_send_callback():
                try:
                    self._send_audio_callback(data)
                except Exception as exc:  # pragma: no cover - network dependent
                    logging.warning("Error sending audio to Deepgram: %s", exc)
                    # Let the connection manager handle reconnection.

        logging.info("Microphone loop stopping")
        self._cleanup()

    def _cleanup(self) -> None:
        try:
            if self._stream is not None:
                self._stream.stop_stream()
                self._stream.close()
        finally:
            self._stream = None

        try:
            if self._pa is not None:
                self._pa.terminate()
        finally:
            self._pa = None

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)


class VoiceTyper:
    """Manages Deepgram connection, microphone streaming, and keystroke typing."""

    def __init__(self, model: str = "nova-2") -> None:
        api_key = os.getenv("DEEPGRAM_API_KEY")
        if not api_key:
            logging.error("DEEPGRAM_API_KEY is not set. Create a .env file with your key.")
            sys.exit(1)

        self._deepgram = DeepgramClient()

        self._model = model
        self._dg_connection = None
        self._dg_lock = threading.Lock()

        self._stop_event = threading.Event()
        self._listening_flag = threading.Event()
        self._mic = MicrophoneStreamer(self._send_audio, self._should_stream_audio, self._stop_event)
        self._ptt_active = False  # Initialize PTT state before signals

        # Setup signal handler for toggling listening (SIGUSR1)
        signal.signal(signal.SIGUSR1, self._handle_toggle_signal)
        # Setup signal handler for PTT (SIGUSR2)
        signal.signal(signal.SIGUSR2, self._handle_ptt_signal)

        self._reconnect_lock = threading.Lock()
        self._reconnecting = False
        self._connection_active = False
        
        # Deduplication and thread safety for typing
        self._typing_lock = threading.Lock()
        self._last_transcript = ""
        self._last_transcript_time = 0
        
        # Track empty transcripts to detect stale connection
        self._empty_transcript_count = 0
        self._last_successful_transcript_time = time.time()
        
        # CIMCO AI mode (F9 toggles)
        self._cimco_mode = False
        self._cimco_speaking = False
        self._cimco_history = []
        
        # Initial status write
        self._update_status_file()

    def _update_status_file(self):
        """Write current state to /tmp/voice_typer_status."""
        state = "ON" if self._listening_flag.is_set() else "OFF"
        try:
            with open("/tmp/voice_typer_status", "w") as f:
                f.write(state)
        except Exception as e:
            logging.warning("Failed to write status file: %s", e)

    def _should_stream_audio(self) -> bool:
        """Return True if we should be streaming audio (Toggle ON or PTT held)."""
        return self._listening_flag.is_set() or self._ptt_active

    # ------------------------------------------------------------------
    # Deepgram connection management (v5.x SDK with context manager)
    # ------------------------------------------------------------------

    def _run_streaming_loop(self) -> None:
        """Main streaming loop using v5.x SDK context manager pattern."""
        backoff = 1.0
        max_backoff = 30.0

        while not self._stop_event.is_set():
            try:
                logging.info("Connecting to Deepgram streaming (model=%s)...", self._model)
                
                with self._deepgram.listen.v1.connect(
                    model=self._model,
                    language="en-US",
                    smart_format=True,
                    punctuate=True,
                    encoding="linear16",
                    channels=CHANNELS,
                    sample_rate=SAMPLE_RATE,
                    interim_results=True,
                    utterance_end_ms="1000",
                    vad_events=True,
                    endpointing=200,
                ) as connection:
                    logging.info("Connected to Deepgram streaming!")
                    
                    # Register event handlers
                    connection.on(EventType.OPEN, self._on_open)
                    connection.on(EventType.MESSAGE, self._on_message)
                    connection.on(EventType.ERROR, self._on_error)
                    connection.on(EventType.CLOSE, self._on_close)
                    
                    # Store connection reference for send_audio
                    with self._dg_lock:
                        self._dg_connection = connection
                        self._connection_active = True
                    
                    # Start listening for events
                    connection.start_listening()
                    
                    # Reset backoff on successful connection
                    backoff = 1.0
                    
                    # Keep the connection alive - events handle messages
                    while not self._stop_event.is_set() and self._connection_active:
                        try:
                            # Check for stale connection (many empty transcripts or long silence)
                            time_since_success = time.time() - self._last_successful_transcript_time
                            if self._empty_transcript_count > 10 and time_since_success > 30:
                                logging.warning("Connection seems stale (%d empty transcripts, %.0fs since last success) - reconnecting",
                                              self._empty_transcript_count, time_since_success)
                                self._empty_transcript_count = 0
                                break  # Exit loop to trigger reconnection
                            
                            # Send keepalive every 5 seconds
                            try:
                                connection.send_keepalive()
                            except Exception:
                                pass  # Ignore keepalive errors
                            
                            time.sleep(5.0)
                        except Exception as e:
                            if "closed" in str(e).lower():
                                logging.warning("WebSocket closed")
                                break
                            logging.debug("error: %s", e)
                    
                    with self._dg_lock:
                        self._connection_active = False
                        self._dg_connection = None

            except Exception as exc:
                logging.error("Failed to connect to Deepgram: %s", exc)
                with self._dg_lock:
                    self._connection_active = False
                    self._dg_connection = None
                
                if not self._stop_event.is_set():
                    logging.info("Retrying in %.1f seconds...", backoff)
                    time.sleep(backoff)
                    backoff = min(backoff * 2, max_backoff)

    def _on_open(self, *args, **kwargs):
        """Called when WebSocket opens."""
        logging.info("Deepgram connection opened")

    def _on_message(self, message, *args, **kwargs):
        """Called when a message is received from Deepgram."""
        self._handle_message(message)

    def _handle_message(self, message):
        """Process a message from Deepgram."""
        try:
            # Handle UtteranceEnd - reset state for next utterance
            msg_type = getattr(message, 'type', '')
            if msg_type == 'UtteranceEnd' or (hasattr(message, '__class__') and 'UtteranceEnd' in message.__class__.__name__):
                logging.debug("UtteranceEnd received - ready for next utterance")
                self._empty_transcript_count = 0  # Reset on utterance boundary
                return
            
            # Handle transcript messages
            if hasattr(message, 'channel') and hasattr(message.channel, 'alternatives'):
                alternatives = message.channel.alternatives
                if alternatives and len(alternatives) > 0:
                    transcript = alternatives[0].transcript
                    if transcript and transcript.strip():
                        # Process both is_final AND speech_final transcripts
                        # is_final = end of a phrase, speech_final = end of utterance (after pause)
                        is_final = getattr(message, 'is_final', False)
                        speech_final = getattr(message, 'speech_final', False)
                        
                        if is_final or speech_final:
                            clean_transcript = transcript.strip()
                            current_time = time.time()
                            
                            # Track successful transcripts
                            self._last_successful_transcript_time = current_time
                            self._empty_transcript_count = 0
                            
                            # Thread-safe deduplication
                            with self._typing_lock:
                                # Skip if same transcript within 3 seconds
                                if (clean_transcript.lower() == self._last_transcript.lower() and 
                                    current_time - self._last_transcript_time < 3.0):
                                    logging.debug("Duplicate ignored: %s", clean_transcript)
                                    return
                                
                                self._last_transcript = clean_transcript
                                self._last_transcript_time = current_time
                                
                                # Route based on mode
                                if self._cimco_mode:
                                    logging.info("🤖 CIMCO: %s", clean_transcript)
                                    threading.Thread(
                                        target=self._handle_cimco_query,
                                        args=(clean_transcript,),
                                        daemon=True
                                    ).start()
                                else:
                                    logging.info("Typing: %s", clean_transcript)
                                    self._type_text(clean_transcript + " ")
            # Track empty final transcripts (sign of stale connection)
            if hasattr(message, 'channel') and hasattr(message.channel, 'alternatives'):
                is_final = getattr(message, 'is_final', False)
                if is_final:
                    alternatives = message.channel.alternatives
                    if not alternatives or not alternatives[0].transcript.strip():
                        self._empty_transcript_count += 1
                        if self._empty_transcript_count % 5 == 0:
                            logging.debug("Empty transcript count: %d", self._empty_transcript_count)
        except Exception as exc:
            logging.debug("Error processing message: %s", exc)
    
    def _handle_cimco_query(self, user_text: str):
        """Handle a query in CIMCO AI mode."""
        import json
        import re
        import urllib.request
        
        OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
        
        SYSTEM_PROMPT = '''You are CIMCO, a helpful AI assistant for an industrial scrapyard inventory system.
Be concise - workers are busy. Answer questions about inventory, equipment, and parts.
If asked about specific inventory data, explain you can help once connected to the database.
Keep responses under 2 sentences.'''
        
        try:
            # Build messages
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            messages.extend(self._cimco_history[-4:])  # Last 2 exchanges
            messages.append({"role": "user", "content": user_text})
            
            # Call Ollama
            data = json.dumps({
                "model": OLLAMA_MODEL,
                "messages": messages,
                "stream": False
            }).encode('utf-8')
            
            req = urllib.request.Request(
                f"{OLLAMA_URL}/api/chat",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))
                reply = result.get("message", {}).get("content", "Sorry, no response.")
            
            logging.info("🤖 Reply: %s", reply)
            
            # Update history
            self._cimco_history.append({"role": "user", "content": user_text})
            self._cimco_history.append({"role": "assistant", "content": reply})
            
            # Speak response (mute mic while speaking)
            self._cimco_speaking = True
            try:
                self._speak_response(reply)
            finally:
                time.sleep(0.3)
                self._cimco_speaking = False
                
        except Exception as e:
            logging.error("CIMCO error: %s", e)
    
    def _speak_response(self, text: str):
        """Speak text using Deepgram TTS."""
        import subprocess
        import tempfile
        import urllib.request
        
        api_key = os.getenv("DEEPGRAM_API_KEY", "")
        if not api_key:
            return
        
        try:
            url = "https://api.deepgram.com/v1/speak?model=aura-asteria-en"
            data = json.dumps({"text": text}).encode('utf-8')
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Authorization": f"Token {api_key}",
                    "Content-Type": "application/json"
                },
                method="POST"
            )
            
            with urllib.request.urlopen(req, timeout=30) as response:
                audio = response.read()
            
            # Play audio
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(audio)
                temp_path = f.name
            
            subprocess.run(["mpv", "--no-video", "--really-quiet", temp_path], timeout=30)
            os.unlink(temp_path)
        except Exception as e:
            logging.error("TTS error: %s", e)

    def _on_error(self, error, *args, **kwargs):
        """Called on error."""
        logging.error("Deepgram error: %s", error)

    def _on_close(self, *args, **kwargs):
        """Called when connection closes."""
        logging.warning("Deepgram connection closed")
        with self._dg_lock:
            self._connection_active = False

    def _send_audio(self, data: bytes) -> None:
        with self._dg_lock:
            conn = self._dg_connection
            active = self._connection_active
        if conn is None or not active:
            return
        try:
            conn.send_media(data)
        except Exception as exc:  # pragma: no cover - network dependent
            logging.warning("Deepgram send failed: %s", exc)

    # ------------------------------------------------------------------
    # Typing logic
    # ------------------------------------------------------------------

    def _type_text(self, text: str) -> None:
        """Type text into the currently focused window using xdotool."""
        if not text:
            return
        try:
            import subprocess
            logging.debug("Typing text: '%s'", text)
            # Use xdotool which is more reliable on Linux
            # --clearmodifiers prevents modifier key interference
            subprocess.run(
                ['xdotool', 'type', '--clearmodifiers', '--', text],
                check=True,
                timeout=10
            )
        except Exception as exc:  # pragma: no cover - system dependent
            logging.error("Failed to simulate keystrokes: %s", exc)

    # ------------------------------------------------------------------
    # Hotkey handling
    # ------------------------------------------------------------------

    def _handle_toggle_signal(self, signum, frame):
        """Toggle listening state on SIGUSR1."""
        if self._listening_flag.is_set():
            self._listening_flag.clear()
            logging.info("Signal received: Listening PAUSED")
        else:
            self._listening_flag.set()
            logging.info("Signal received: Listening RESUMED")
        self._update_status_file()

    def _handle_ptt_signal(self, signum, frame):
        """Toggle PTT state on SIGUSR2."""
        self._ptt_active = not self._ptt_active
        if self._ptt_active:
             logging.info("Signal received: PTT ACTIVE")
        else:
             logging.info("Signal received: PTT RELEASED")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> None:
        logging.info("Starting VoiceTyper (Deepgram model=%s)", self._model)
        logging.info("Press F8 to toggle listening on/off. Ctrl+C to exit.")

        # Start microphone capture
        self._mic.start()

        # Start hotkey listener
        # No internal hotkey listener - relying on external signals

        # Run the streaming loop (blocking, with reconnection)
        try:
            self._run_streaming_loop()
        except KeyboardInterrupt:
            logging.info("KeyboardInterrupt received, shutting down...")
        finally:
            self.stop()

    def stop(self) -> None:
        self._stop_event.set()
        self._mic.stop()

        with self._dg_lock:
            if self._dg_connection is not None:
                try:
                    self._dg_connection.send_close_stream()
                except Exception:  # pragma: no cover - network dependent
                    pass
                self._dg_connection = None

        # Remove lock file
        lock_file = os.path.join(os.path.dirname(__file__), "voice_typer.lock")
        try:
            os.remove(lock_file)
        except FileNotFoundError:
            pass


def enforce_singleton():
    """Ensure only one instance runs. Kills older instances found in lock file."""
    lock_file = "/tmp/voice_typer.pid"
    
    # Check for existing instance
    if os.path.exists(lock_file):
        try:
            with open(lock_file, "r") as f:
                old_pid = int(f.read().strip())
            
            if psutil.pid_exists(old_pid):
                logging.warning(f"Found old instance (PID {old_pid}). Terminating it...")
                try:
                    p = psutil.Process(old_pid)
                    p.terminate()
                    p.wait(timeout=3)
                except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                    # Force kill if needed
                    if psutil.pid_exists(old_pid):
                         os.kill(old_pid, signal.SIGKILL)
                logging.info("Old instance terminated.")
        except Exception as e:
            logging.warning(f"Error checking lock file: {e}")

    # Register our PID
    try:
        with open(lock_file, "w") as f:
            f.write(str(os.getpid()))
        
        # Cleanup on exit
        def remove_lock():
            try:
                if os.path.exists(lock_file):
                    os.remove(lock_file)
            except: pass
        atexit.register(remove_lock)
        
    except Exception as e:
        logging.error(f"Failed to write lock file: {e}")
        sys.exit(1)

def main() -> None:
    logging.basicConfig(
        level=logging.DEBUG,
        format="[%(asctime)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    
    enforce_singleton()

    typer = VoiceTyper(model="nova-2")
    typer.run()


if __name__ == "__main__":
    main()