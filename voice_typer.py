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
from pynput import keyboard

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
        self._listening_flag.set()  # Auto-start listening
        self._mic = MicrophoneStreamer(self._send_audio, self._should_stream_audio, self._stop_event)
        self._ptt_active = False  # Initialize PTT state before signals

        # Setup signal handler for toggling listening (SIGUSR1)
        signal.signal(signal.SIGUSR1, self._handle_toggle_signal)
        # Setup signal handler for PTT (SIGUSR2)
        signal.signal(signal.SIGUSR2, self._handle_ptt_signal)
        # Setup signal handler for OpenClaw mode toggle (SIGRTMIN)
        signal.signal(signal.SIGRTMIN, self._handle_openclaw_toggle_signal)

        self._reconnect_lock = threading.Lock()
        self._reconnecting = False
        self._connection_active = False
        
        # Deduplication and thread safety for typing
        self._typing_lock = threading.Lock()
        self._last_transcript = ""
        self._last_transcript_time = 0
        
        # Buffer for streaming typing (interim results)
        self._current_utterance_typed = ""
        
        # Track empty transcripts to detect stale connection
        self._empty_transcript_count = 0
        self._last_successful_transcript_time = time.time()
        
        # OpenClaw AI mode (F9 toggles)
        self._openclaw_mode = False
        self._openclaw_speaking = False
        
        # Keyboard listener for Alt PTT
        self._alt_keys = {keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt}
        self._alt_pressed = False
        self._keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release
        )
        
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

    def _on_key_press(self, key):
        if key in self._alt_keys and not self._alt_pressed:
            self._alt_pressed = True
            self._ptt_active = True
            logging.info("Alt key pressed - PTT ACTIVE")
            return False  # Suppress Alt key to prevent focus shift
        return True

    def _on_key_release(self, key):
        if key in self._alt_keys and self._alt_pressed:
            self._alt_pressed = False
            self._ptt_active = False
            # Reset transcript buffer when PTT releases
            with self._typing_lock:
                self._current_utterance_typed = ""
            logging.info("Alt key released - PTT RELEASED")
            return False  # Suppress Alt key to prevent focus shift
        return True

    # ------------------------------------------------------------------
    # Deepgram connection management (v5.x SDK with context manager)
    # ------------------------------------------------------------------

    def _run_streaming_session(self) -> None:
        """Run a single streaming session. Returns when paused or stopped."""
        backoff = 1.0
        max_backoff = 30.0

        logging.info("Connecting to Deepgram streaming (model=%s)...", self._model)
        
        try:
            with self._deepgram.listen.v1.connect(
                model=self._model,
                language="en-US",
                smart_format="true",
                punctuate="true",
                dictation="true",
                encoding="linear16",
                channels=str(CHANNELS),
                sample_rate=str(SAMPLE_RATE),
                interim_results="true",
                utterance_end_ms="1000",
                vad_events="true",
                endpointing="500",
            ) as connection:
                logging.info("Connected to Deepgram streaming!")
                
                # Register event handlers
                connection.on(EventType.OPEN, self._on_open)
                connection.on(EventType.MESSAGE, self._on_message)
                connection.on(EventType.ERROR, self._on_error)
                connection.on(EventType.CLOSE, self._on_close)
                
                with self._dg_lock:
                    self._dg_connection = connection
                    self._connection_active = True
                
                connection.start_listening()
                
                # Wait loop - exit if paused or stopped
                while not self._stop_event.is_set():
                    # Check if we should still be listening (toggle OR PTT)
                    if not self._listening_flag.is_set() and not self._ptt_active:
                        logging.info("Paused - closing connection.")
                        break

                    # Check connection health
                    if not self._connection_active:
                         logging.warning("Connection lost unexpectedly.")
                         break

                    # Check for stale connection
                    time_since_success = time.time() - self._last_successful_transcript_time
                    if self._empty_transcript_count > 10 and time_since_success > 30:
                        logging.warning("Connection stale - reconnecting...")
                        break
                    
                    try:
                        connection.send_keepalive()
                    except: pass
                    
                    time.sleep(0.5)
                
                # Cleanup connection for this session
                with self._dg_lock:
                    self._connection_active = False
                    self._dg_connection = None

        except Exception as exc:
            logging.error("Deepgram connection error: %s", exc)
            if not self._stop_event.is_set() and self._listening_flag.is_set():
                time.sleep(backoff) # Simple backoff if error occurred

    def _on_open(self, *args, **kwargs):
        """Called when WebSocket opens."""
        logging.info("Deepgram connection opened")

    def _on_message(self, message, *args, **kwargs):
        """Called when a message is received from Deepgram."""
        self._handle_message(message)

    def _handle_message(self, message):
        """Process a message from Deepgram."""
        try:
            # Handle transcript messages
            if hasattr(message, 'channel') and hasattr(message.channel, 'alternatives'):
                alternatives = message.channel.alternatives
                if alternatives and len(alternatives) > 0:
                    transcript = alternatives[0].transcript
                    if transcript and transcript.strip():
                        speech_final = getattr(message, 'speech_final', False)
                        is_final = getattr(message, 'is_final', False)
                        clean_transcript = transcript.strip()
                        
                        # Only type FINAL results (not interim) to avoid duplicates
                        if speech_final or is_final:
                            with self._typing_lock:
                                # Skip if same as last typed
                                if clean_transcript.lower() != self._last_transcript.lower():
                                    self._last_transcript = clean_transcript
                                    text_to_type = clean_transcript + " "
                                    if not self._openclaw_mode:
                                        logging.info("Typing: %s", clean_transcript)
                                        self._type_text(text_to_type)
        except Exception as exc:
            logging.error("Error processing message: %s", exc)
    
    def _type_transcript(self, text_to_type: str, full_transcript: str, current_time: float, interim: bool = False):
        """Type transcript text, handling deduplication and routing."""
        if not text_to_type:
            return
            
        # Check for duplicates against last final transcript
        if (full_transcript.lower() == self._last_transcript.lower() and 
            current_time - self._last_transcript_time < 3.0):
            logging.debug("Duplicate ignored: %s", full_transcript)
            return
        
        # Update last transcript tracking for final results
        if not interim:
            self._last_transcript = full_transcript
            self._last_transcript_time = current_time
        
        # Route based on mode
        if self._openclaw_mode:
            if not interim:  # Only send final to OpenClaw
                logging.info("🦞 OpenClaw: %s", full_transcript)
                threading.Thread(
                    target=self._handle_openclaw_query,
                    args=(full_transcript,),
                    daemon=True
                ).start()
        else:
            if interim:
                logging.debug("Typing interim: '%s'", text_to_type)
            else:
                logging.info("Typing: %s", full_transcript)
            self._type_text(text_to_type)
    
    def _handle_openclaw_query(self, user_text: str):
        """Handle a query via OpenClaw (GLM-5)."""
        import subprocess
        
        try:
            # Use openclaw task for one-shot queries
            result = subprocess.run(
                ["openclaw", "task", "--no-stream", "--quiet", user_text],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=os.path.expanduser("~")
            )
            
            reply = result.stdout.strip() if result.stdout else "No response from OpenClaw."
            if result.returncode != 0 and result.stderr:
                logging.warning("OpenClaw stderr: %s", result.stderr)
            
            logging.info("🦞 Reply: %s", reply[:200] + "..." if len(reply) > 200 else reply)
            
            # Speak response (mute mic while speaking)
            self._openclaw_speaking = True
            try:
                self._speak_response(reply)
            finally:
                time.sleep(0.3)
                self._openclaw_speaking = False
                
        except subprocess.TimeoutExpired:
            logging.error("OpenClaw timeout")
        except Exception as e:
            logging.error("OpenClaw error: %s", e)
    
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

    def _handle_openclaw_toggle_signal(self, signum, frame):
        """Toggle OpenClaw AI mode on SIGRTMIN (F9)."""
        self._openclaw_mode = not self._openclaw_mode
        if self._openclaw_mode:
            logging.info("🦞 OpenClaw mode ENABLED - voice commands will be sent to GLM-5")
        else:
            logging.info("🦞 OpenClaw mode DISABLED - back to typing mode")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> None:
        logging.info("Starting VoiceTyper (Deepgram model=%s)", self._model)
        logging.info("Press F8 to toggle listening on/off. Alt for Push-to-Talk. Ctrl+C to exit.")

        # Start microphone capture
        self._mic.start()

        # Start hotkey listener
        self._keyboard_listener.start()

        # Main loop
        try:
            while not self._stop_event.is_set():
                if self._listening_flag.is_set() or self._ptt_active:
                    # We are ON or PTT held - run a streaming session
                    self._run_streaming_session()
                else:
                    # We are OFF - wait for signal
                    time.sleep(0.1)
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
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # Suppress overly verbose SDK debug logs
    for logger_name in ["deepgram", "deepgram.clients.listen", "websocket", "urllib3", "asyncio"]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
    
    enforce_singleton()

    typer = VoiceTyper(model="nova-2")
    typer.run()


if __name__ == "__main__":
    main()