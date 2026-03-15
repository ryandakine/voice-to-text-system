#!/usr/bin/env python3
"""VoiceTyper v2.0 - Deepgram-powered voice-to-text with advanced features.

Features
--------
- Configurable keyboard shortcuts
- Transcript history with SQLite
- Voice command support
- Audio device selection
- Multiple export formats (TXT, JSON, CSV, SRT, Markdown)
- System tray toggle
- Push-to-talk (Alt)
- OpenClaw AI mode (F9)
"""

import json
import logging
import os
import sys
import threading
import time
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime

from pynput import keyboard
import pyaudio
from dotenv import load_dotenv
import signal
import psutil
import atexit

# Load .env BEFORE importing deepgram SDK
_script_dir = os.path.dirname(os.path.abspath(__file__))
_env_path = os.path.join(_script_dir, ".env")
load_dotenv(_env_path)

from deepgram import DeepgramClient
from deepgram.core.events import EventType

# Import new modules
from config_manager import ConfigManager
from history_manager import HistoryManager
from audio_manager import AudioManager
from voice_commands import VoiceCommandProcessor, VoiceCommand
from export_manager import ExportManager

# Audio settings
SAMPLE_RATE = 16000
CHANNELS = 1
FORMAT = pyaudio.paInt16
CHUNK_SIZE = 1024


class MicrophoneStreamer:
    """Background thread for microphone capture."""
    
    def __init__(self, send_audio_callback, should_send_callback, 
                 stop_event: threading.Event, audio_manager: AudioManager):
        self._send_audio_callback = send_audio_callback
        self._should_send_callback = should_send_callback
        self._stop_event = stop_event
        self._audio_manager = audio_manager
        
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
        
        # Show available devices
        self._audio_manager.print_devices()
        
        # Auto-select recommended device
        if self._audio_manager.get_selected_device() is None:
            rec = self._audio_manager.get_recommended_device()
            if rec is not None:
                self._audio_manager.select_device(rec)
        
        device_info = self._audio_manager.get_device_info()
        if device_info:
            logging.info(f"Using audio device: {device_info['name']}")
        
        try:
            self._stream = self._audio_manager.open_stream(
                format=FORMAT,
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                frames_per_buffer=CHUNK_SIZE
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
                logging.warning("Error reading from microphone: %s", exc)
                time.sleep(0.1)
                continue

            if self._should_send_callback():
                try:
                    self._send_audio_callback(data)
                except Exception as exc:
                    logging.warning("Error sending audio: %s", exc)

        logging.info("Microphone loop stopping")
        self._cleanup()

    def _cleanup(self) -> None:
        try:
            if self._stream:
                self._stream.stop_stream()
                self._stream.close()
        finally:
            self._stream = None

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)


class VoiceTyper:
    """Main VoiceTyper class with all v2.0 features."""

    def __init__(self, model: str = "nova-2") -> None:
        api_key = os.getenv("DEEPGRAM_API_KEY")
        if not api_key:
            logging.error("DEEPGRAM_API_KEY is not set.")
            sys.exit(1)

        # Initialize managers
        self.config = ConfigManager()
        self.history = HistoryManager(
            retention_days=self.config.get('history.retention_days', 90)
        )
        self.audio_manager = AudioManager()
        self.exporter = ExportManager(
            output_dir=self.config.get('export.output_dir', '~/Documents/VoiceTyper')
        )
        
        # Initialize voice commands
        self.command_processor = VoiceCommandProcessor(
            enabled=self.config.get('voice_commands.enabled', True),
            prefix=self.config.get('voice_commands.prefix', 'computer')
        )
        self._register_voice_commands()

        self._deepgram = DeepgramClient()
        self._model = model
        self._dg_connection = None
        self._dg_lock = threading.Lock()

        self._stop_event = threading.Event()
        self._listening_flag = threading.Event()
        self._listening_flag.set()
        
        self._mic = MicrophoneStreamer(
            self._send_audio, 
            self._should_stream_audio, 
            self._stop_event,
            self.audio_manager
        )
        self._ptt_active = False

        # Setup signal handlers
        signal.signal(signal.SIGUSR1, self._handle_toggle_signal)
        signal.signal(signal.SIGUSR2, self._handle_ptt_signal)
        signal.signal(signal.SIGRTMIN, self._handle_openclaw_toggle_signal)

        self._reconnect_lock = threading.Lock()
        self._connection_active = False
        
        self._typing_lock = threading.Lock()
        self._last_transcript = ""
        self._last_transcript_time = 0
        self._current_utterance_typed = ""
        self._empty_transcript_count = 0
        self._last_successful_transcript_time = time.time()
        
        self._openclaw_mode = False
        self._openclaw_speaking = False
        
        # Load shortcut keys from config
        self._setup_shortcuts()
        
        self._update_status_file()

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts from config."""
        # Map string names to key objects
        key_map = {
            'f8': keyboard.Key.f8,
            'f9': keyboard.Key.f9,
            'f10': keyboard.Key.f10,
            'esc': keyboard.Key.esc,
            'alt': keyboard.Key.alt,
            'alt_l': keyboard.Key.alt_l,
            'alt_r': keyboard.Key.alt_r,
            'ctrl': keyboard.Key.ctrl,
            'ctrl_l': keyboard.Key.ctrl_l,
            'ctrl_r': keyboard.Key.ctrl_r,
            'shift': keyboard.Key.shift,
            'shift_l': keyboard.Key.shift_l,
            'shift_r': keyboard.Key.shift_r,
        }
        
        # Get shortcuts from config
        ptt_keys = self.config.get_ptt_keys()
        self._alt_keys = set()
        for key_name in ptt_keys:
            key_name = key_name.lower()
            if key_name in key_map:
                self._alt_keys.add(key_map[key_name])
        
        if not self._alt_keys:
            self._alt_keys = {keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt}
        
        self._alt_pressed = False
        self._keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release
        )

    def _register_voice_commands(self):
        """Register handlers for voice commands."""
        self.command_processor.register_handler(VoiceCommand.STOP_LISTENING, self._cmd_stop)
        self.command_processor.register_handler(VoiceCommand.START_LISTENING, self._cmd_start)
        self.command_processor.register_handler(VoiceCommand.CLEAR_LAST, self._cmd_clear_last)
        self.command_processor.register_handler(VoiceCommand.EXPORT, self._cmd_export)
        self.command_processor.register_handler(VoiceCommand.HELP, self._cmd_help)
        self.command_processor.register_handler(VoiceCommand.TOGGLE_MODE, self._cmd_toggle_mode)

    def _cmd_stop(self):
        """Stop listening command."""
        self._listening_flag.clear()
        self._update_status_file()
        logging.info("🛑 Voice command: Listening PAUSED")

    def _cmd_start(self):
        """Start listening command."""
        self._listening_flag.set()
        self._update_status_file()
        logging.info("▶️ Voice command: Listening RESUMED")

    def _cmd_toggle_mode(self):
        """Toggle mode command."""
        self._handle_openclaw_toggle_signal(None, None)

    def _cmd_clear_last(self):
        """Clear last transcript command."""
        # This would need xdotool to delete text
        logging.info("🗑️ Voice command: Clear last (use Ctrl+Z)")

    def _cmd_export(self):
        """Export transcript command."""
        self._quick_export()

    def _cmd_help(self):
        """Show help command."""
        help_text = self.command_processor.get_help_text()
        print("\n" + help_text + "\n")
        logging.info("ℹ️ Voice command: Help displayed")

    def _update_status_file(self):
        """Write current state to /tmp/voice_typer_status."""
        state = "ON" if self._listening_flag.is_set() else "OFF"
        try:
            with open("/tmp/voice_typer_status", "w") as f:
                f.write(state)
        except Exception as e:
            logging.warning("Failed to write status file: %s", e)

    def _should_stream_audio(self) -> bool:
        """Return True if we should stream audio."""
        return self._listening_flag.is_set() or self._ptt_active

    def _on_key_press(self, key):
        if key in self._alt_keys and not self._alt_pressed:
            self._alt_pressed = True
            self._ptt_active = True
            logging.info("🎤 Alt key pressed - PTT ACTIVE")
            return False
        return True

    def _on_key_release(self, key):
        if key in self._alt_keys and self._alt_pressed:
            self._alt_pressed = False
            self._ptt_active = False
            with self._typing_lock:
                self._current_utterance_typed = ""
            logging.info("🔇 Alt key released - PTT RELEASED")
            return False
        return True

    def _run_streaming_session(self) -> None:
        """Run a single streaming session."""
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
                
                connection.on(EventType.OPEN, self._on_open)
                connection.on(EventType.MESSAGE, self._on_message)
                connection.on(EventType.ERROR, self._on_error)
                connection.on(EventType.CLOSE, self._on_close)
                
                with self._dg_lock:
                    self._dg_connection = connection
                    self._connection_active = True
                
                connection.start_listening()
                
                while not self._stop_event.is_set():
                    if not self._listening_flag.is_set() and not self._ptt_active:
                        logging.info("Paused - closing connection.")
                        break

                    if not self._connection_active:
                        logging.warning("Connection lost unexpectedly.")
                        break

                    time_since_success = time.time() - self._last_successful_transcript_time
                    if self._empty_transcript_count > 10 and time_since_success > 30:
                        logging.warning("Connection stale - reconnecting...")
                        break
                    
                    try:
                        connection.send_keepalive()
                    except:
                        pass
                    
                    time.sleep(0.5)
                
                with self._dg_lock:
                    self._connection_active = False
                    self._dg_connection = None

        except Exception as exc:
            logging.error("Deepgram connection error: %s", exc)
            if not self._stop_event.is_set() and self._listening_flag.is_set():
                time.sleep(1.0)

    def _on_open(self, *args, **kwargs):
        logging.info("Deepgram connection opened")

    def _on_message(self, message, *args, **kwargs):
        self._handle_message(message)

    def _handle_message(self, message):
        """Process transcript messages."""
        try:
            if hasattr(message, 'channel') and hasattr(message.channel, 'alternatives'):
                alternatives = message.channel.alternatives
                if alternatives and len(alternatives) > 0:
                    transcript = alternatives[0].transcript
                    if transcript and transcript.strip():
                        speech_final = getattr(message, 'speech_final', False)
                        is_final = getattr(message, 'is_final', False)
                        clean_transcript = transcript.strip()
                        
                        # Try to process as voice command first
                        if speech_final or is_final:
                            command = self.command_processor.process(clean_transcript)
                            if command:
                                return  # Don't type commands
                        
                        # Only type FINAL results
                        if speech_final or is_final:
                            with self._typing_lock:
                                if clean_transcript.lower() != self._last_transcript.lower():
                                    self._last_transcript = clean_transcript
                                    self._last_transcript_time = time.time()
                                    
                                    # Save to history
                                    self.history.add(
                                        clean_transcript,
                                        duration_ms=getattr(message, 'duration', None)
                                    )
                                    
                                    # Type or send to OpenClaw
                                    if self._openclaw_mode:
                                        logging.info("🦞 OpenClaw: %s", clean_transcript)
                                        threading.Thread(
                                            target=self._handle_openclaw_query,
                                            args=(clean_transcript,),
                                            daemon=True
                                        ).start()
                                    else:
                                        logging.info("Typing: %s", clean_transcript)
                                        self._type_text(clean_transcript + " ")
        except Exception as exc:
            logging.error("Error processing message: %s", exc)

    def _handle_openclaw_query(self, user_text: str):
        """Handle OpenClaw query."""
        import subprocess
        try:
            result = subprocess.run(
                ["openclaw", "task", "--no-stream", "--quiet", user_text],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=os.path.expanduser("~")
            )
            reply = result.stdout.strip() if result.stdout else "No response."
            logging.info("🦞 Reply: %s", reply[:200] + "..." if len(reply) > 200 else reply)
            
            self._openclaw_speaking = True
            try:
                self._speak_response(reply)
            finally:
                time.sleep(0.3)
                self._openclaw_speaking = False
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
                url, data=data,
                headers={"Authorization": f"Token {api_key}", "Content-Type": "application/json"},
                method="POST"
            )
            
            with urllib.request.urlopen(req, timeout=30) as response:
                audio = response.read()
            
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(audio)
                temp_path = f.name
            
            subprocess.run(["mpv", "--no-video", "--really-quiet", temp_path], timeout=30)
            os.unlink(temp_path)
        except Exception as e:
            logging.error("TTS error: %s", e)

    def _on_error(self, error, *args, **kwargs):
        logging.error("Deepgram error: %s", error)

    def _on_close(self, *args, **kwargs):
        logging.warning("Deepgram connection closed")
        with self._dg_lock:
            self._connection_active = False

    def _send_audio(self, data: bytes) -> None:
        with self._dg_lock:
            conn = self._dg_connection
            active = self._connection_active
        if conn and active:
            try:
                conn.send_media(data)
            except Exception as exc:
                logging.warning("Deepgram send failed: %s", exc)

    def _type_text(self, text: str) -> None:
        """Type text into focused window."""
        if not text:
            return
        try:
            import subprocess
            subprocess.run(
                ['xdotool', 'type', '--clearmodifiers', '--', text],
                check=True,
                timeout=10
            )
        except Exception as exc:
            logging.error("Failed to type: %s", exc)

    def _quick_export(self):
        """Quick export current session."""
        try:
            transcripts = self.history.get_session_transcripts()
            if transcripts:
                path = self.exporter.quick_export(transcripts, 'txt')
                if path:
                    logging.info(f"📁 Exported to: {path}")
                else:
                    logging.warning("Export failed")
            else:
                logging.info("No transcripts to export")
        except Exception as e:
            logging.error(f"Export error: {e}")

    def _handle_toggle_signal(self, signum, frame):
        """Toggle listening state."""
        if self._listening_flag.is_set():
            self._listening_flag.clear()
            logging.info("📵 Listening PAUSED")
        else:
            self._listening_flag.set()
            logging.info("🎧 Listening RESUMED")
        self._update_status_file()

    def _handle_ptt_signal(self, signum, frame):
        """Toggle PTT state."""
        self._ptt_active = not self._ptt_active
        logging.info("PTT %s", "ACTIVE" if self._ptt_active else "RELEASED")

    def _handle_openclaw_toggle_signal(self, signum, frame):
        """Toggle OpenClaw mode."""
        self._openclaw_mode = not self._openclaw_mode
        if self._openclaw_mode:
            logging.info("🦞 OpenClaw mode ENABLED")
        else:
            logging.info("🦞 OpenClaw mode DISABLED")

    def run(self) -> None:
        """Main run loop."""
        logging.info("🎤 Starting VoiceTyper v2.0 (Deepgram model=%s)", self._model)
        logging.info("💡 Press F8 to toggle, Alt for PTT, F9 for OpenClaw, F10 to export")
        logging.info("🗣️ Say 'computer help' for voice commands")

        # Start microphone
        self._mic.start()

        # Start keyboard listener
        self._keyboard_listener.start()

        # Main loop
        try:
            while not self._stop_event.is_set():
                if self._listening_flag.is_set() or self._ptt_active:
                    self._run_streaming_session()
                else:
                    time.sleep(0.1)
        except KeyboardInterrupt:
            logging.info("Shutting down...")
        finally:
            self.stop()

    def stop(self) -> None:
        """Cleanup and stop."""
        self._stop_event.set()
        self._mic.stop()

        with self._dg_lock:
            if self._dg_connection:
                try:
                    self._dg_connection.send_close_stream()
                except:
                    pass
                self._dg_connection = None

        # Remove lock file
        lock_file = os.path.join(os.path.dirname(__file__), "voice_typer.lock")
        try:
            os.remove(lock_file)
        except FileNotFoundError:
            pass


def enforce_singleton():
    """Ensure only one instance runs."""
    lock_file = "/tmp/voice_typer.pid"
    
    if os.path.exists(lock_file):
        try:
            with open(lock_file, "r") as f:
                old_pid = int(f.read().strip())
            
            if psutil.pid_exists(old_pid):
                logging.warning(f"Found old instance (PID {old_pid}). Terminating...")
                try:
                    p = psutil.Process(old_pid)
                    p.terminate()
                    p.wait(timeout=3)
                except:
                    if psutil.pid_exists(old_pid):
                        os.kill(old_pid, signal.SIGKILL)
                logging.info("Old instance terminated.")
        except Exception as e:
            logging.warning(f"Error checking lock file: {e}")

    try:
        with open(lock_file, "w") as f:
            f.write(str(os.getpid()))
        
        def remove_lock():
            try:
                if os.path.exists(lock_file):
                    os.remove(lock_file)
            except:
                pass
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
    # Suppress verbose SDK logs
    for logger_name in ["deepgram", "deepgram.clients.listen", "websocket"]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
    
    enforce_singleton()

    typer = VoiceTyper(model="nova-2")
    typer.run()


if __name__ == "__main__":
    main()
