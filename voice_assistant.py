#!/usr/bin/env python3
"""Antigravity Voice Assistant (Home Assistant Edition).

A voice-enabled AI assistant for Smart Home control.
Uses LOCAL Ollama (phi3:mini) for privacy and speed.
"""

import asyncio
import json
import logging
import os
import re
import sys
import threading
import time
from typing import Optional

import httpx
import pyaudio
from dotenv import load_dotenv

# Load .env
_script_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_script_dir, ".env"))

from deepgram import DeepgramClient
from deepgram.core.events import EventType

# Import tools - ensuring we have control_home
from cimco_tools import CIMCO_TOOLS, execute_tool
from tts_speaker import speak

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Audio settings
SAMPLE_RATE = 48000
CHANNELS = 1
FORMAT = pyaudio.paInt16
CHUNK_SIZE = 1024

# Ollama configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "phi3:mini")

# System prompt
SYSTEM_PROMPT = """You are the Antigravity Smart Home Assistant.
Your job is to control the home environment and assist the user.

You have access to these tools:
- control_home(action, target) - Control devices.
  - action: "unlock", "lock", "turn_on", "turn_off"
  - target: "door", "lights", "music", "bedroom_lights"

When you need to use a tool, respond ONLY with JSON:
{"tool": "tool_name", "args": {"arg1": "value1"}}

Example:
User: "Unlock the front door."
You: {"tool": "control_home", "args": {"action": "unlock", "target": "door"}}

User: "Turn on the lights."
You: {"tool": "control_home", "args": {"action": "turn_on", "target": "lights"}}

If no tool is needed, just answer normally. Be concise.
"""


class MicrophoneStreamer:
    """Background thread that streams microphone audio."""
    
    def __init__(self, send_audio_callback, stop_event: threading.Event):
        self._send_audio_callback = send_audio_callback
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
        
    def _run(self) -> None:
        self._pa = pyaudio.PyAudio()
        
        # Probe for working input device
        self._stream = None
        device_indices = []
        
        # Priority 0: USB Devices (Hardware)
        usb_indices = []
        default_indices = []
        other_indices = []
        
        for i in range(self._pa.get_device_count()):
            try:
                info = self._pa.get_device_info_by_index(i)
                if info["maxInputChannels"] > 0:
                    name = info["name"].lower()
                    if "usb" in name or "cmteck" in name:
                         usb_indices.append(i)
                    elif "pulse" in name or "default" in name:
                         default_indices.append(i)
                    else:
                         other_indices.append(i)
            except Exception:
                continue
        
        # Combine priorities: USB > Pulse/Default > Others
        device_indices = usb_indices + default_indices + other_indices
        
        logger.info(f"Probing devices in order: {device_indices}")
        
        for idx in device_indices:
            try:
                info = self._pa.get_device_info_by_index(idx)
                logger.info(f"Attempting to open device {idx}: {info['name']}...")
                self._stream = self._pa.open(
                    format=FORMAT,
                    channels=CHANNELS,
                    rate=SAMPLE_RATE,
                    input=True,
                    input_device_index=idx,
                    frames_per_buffer=CHUNK_SIZE,
                )
                logger.info(f"✅ Successfully opened device {idx}")
                break
            except Exception as e:
                logger.warning(f"Failed to open device {idx}: {e}")
                continue
        
        if self._stream is None:
            logger.error("❌ Could not find any working input device!")
            self._cleanup()
            return
        
        logger.info("✅ Microphone stream started")
        
        while not self._stop_event.is_set():
            try:
                data = self._stream.read(CHUNK_SIZE, exception_on_overflow=False)
                # DEBUG: Trace first byte to ensure non-silence often
                # if data and data[0] != 0:
                #    logger.debug(f"Audio chunk: {len(data)} bytes")
                self._send_audio_callback(data)
            except Exception as e:
                if not self._stop_event.is_set():
                    logger.debug("Audio read error: %s", e)
                break
        
        self._cleanup()
    
    def _cleanup(self):
        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except:
                pass
        if self._pa:
            try:
                self._pa.terminate()
            except:
                pass


class VoiceAssistant:
    """Main assistant class."""
    
    def __init__(self):
        # Configure Deepgram - rely on env var DEEPGRAM_API_KEY
        self.deepgram = DeepgramClient() 
        
        self._stop_event = threading.Event()
        self.conversation_history = []
        self._dg_connection = None
        self._dg_lock = threading.Lock()
        self._connection_active = False
        self._is_speaking = False
        self._mic = MicrophoneStreamer(self._send_audio, self._stop_event)
    
    def _send_audio(self, data: bytes):
        """Send audio to Deepgram."""
        if self._is_speaking:
            return
            
        # Debug audio levels
        import audioop
        rms = audioop.rms(data, 2)
        if rms > 100:  # Threshold for "not silence"
             if rms > 500: logger.info(f"Audio Level: {rms}") # Only log significant noise
             
        with self._dg_lock:
            conn = self._dg_connection
            active = self._connection_active
        if conn is None or not active:
            return
        try:
            conn.send(data)
            logger.debug("Sent audio bytes") 
        except Exception:
            pass
    
    def _call_ollama_sync(self, messages: list) -> str:
        """Call local Ollama LLM."""
        try:
            import urllib.request
            
            data = json.dumps({
                "model": OLLAMA_MODEL,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": 0.1 # Low temp for tool usage reliability
                }
            }).encode('utf-8')
            
            req = urllib.request.Request(
                f"{OLLAMA_BASE_URL}/api/chat",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result.get("message", {}).get("content", "")
        
        except Exception as e:
            logger.error(f"Ollama call failed: {e}")
            return "System malfuntion."
    
    def _extract_tool_call(self, response: str) -> Optional[dict]:
        """Extract tool call JSON from response."""
        try:
            # Look for JSON block
            match = re.search(r'\{[^{}]*"tool"[^{}]*\}', response)
            if match:
                return json.loads(match.group())
        except json.JSONDecodeError:
            pass
        return None
    
    def _process_query_sync(self, user_text: str) -> str:
        """Process a user query."""
        logger.info(f"User: {user_text}")
        
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(self.conversation_history[-6:])
        messages.append({"role": "user", "content": user_text})
        
        response = self._call_ollama_sync(messages)
        logger.info(f"LLM: {response}")
        
        tool_call = self._extract_tool_call(response)
        if tool_call:
            tool_name = tool_call.get("tool")
            tool_args = tool_call.get("args", {})
            
            logger.info(f"🛠️ Tool call: {tool_name}({tool_args})")
            
            # Execute tool
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(execute_tool(tool_name, tool_args))
            finally:
                loop.close()
            
            logger.info(f"✅ Result: {result}")
            
            # Feed result back to LLM for final response
            messages.append({"role": "assistant", "content": response})
            messages.append({
                "role": "user", 
                "content": f"Tool execution result: {json.dumps(result)}. Reply to the user confirming the action."
            })
            
            final_response = self._call_ollama_sync(messages)
            # Strip any lingering usage of JSON in final response
            final_response = re.sub(r'\{[^{}]*"tool"[^{}]*\}', '', final_response).strip()
            
            self.conversation_history.append({"role": "user", "content": user_text})
            self.conversation_history.append({"role": "assistant", "content": final_response})
            
            return final_response
        
        clean_response = re.sub(r'\{[^{}]*"tool"[^{}]*\}', '', response).strip()
        self.conversation_history.append({"role": "user", "content": user_text})
        self.conversation_history.append({"role": "assistant", "content": clean_response})
        return clean_response
    
    def _handle_transcript(self, transcript: str):
        """Handle a finalized transcript."""
        if not transcript.strip():
            return
        
        # Simple Wake Word check (optional, but good for reducing false triggers)
        # For now, we process everything since it's a dedicated device, 
        # but in production we might want "Hey Computer" or similar.
        
        response = self._process_query_sync(transcript)
        if response:
            logger.info(f"🗣️ Speaking: {response}")
            self._is_speaking = True
            try:
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(speak(response))
                finally:
                    loop.close()
            except Exception as e:
                logger.error(f"TTS Error: {e}")
            finally:
                time.sleep(0.5)
                self._is_speaking = False
    
    def _on_message(self, result, **kwargs):
        """Called when a message is received from Deepgram."""
        try:
            sentence = result.channel.alternatives[0].transcript
            if len(sentence) == 0:
                return
                
            if result.is_final:
                logger.info(f"🎤 Heard: {sentence}")
                threading.Thread(
                    target=self._handle_transcript,
                    args=(sentence,),
                    daemon=True
                ).start()
        except Exception as e:
            logger.debug(f"Error processing message: {e}")
    
    def _on_error(self, error, **kwargs):
        logger.error(f"Deepgram error: {error}")
    
    def _on_close(self, close, **kwargs):
        logger.info("Deepgram connection closed")
        with self._dg_lock:
            self._connection_active = False
    
    def _on_open(self, open, **kwargs):
        logger.info("Deepgram connection opened")
    
    def run(self):
        """Main run loop."""
        logger.info("=" * 50)
        logger.info("Antigravity Smart Home Assistant")
        logger.info(f"Model: {OLLAMA_MODEL}")
        logger.info("=" * 50)
        logger.info("Ready. Speak clearly.")
        
        # Start microphone
        self._mic.start()
        
        while not self._stop_event.is_set():
            try:
                # Deepgram Live Options
                options = {
                    "model": "nova-2",
                    "language": "en-US",
                    "smart_format": True,
                    "encoding": "linear16",
                    "channels": CHANNELS,
                    "sample_rate": SAMPLE_RATE,
                    "interim_results": False,
                    "vad_events": True,
                }
                
                logger.info("Connecting to Deepgram...")
                # Connect using v1.connect (Context Manager)
                # We use the context manager to ensure proper cleanup
                with self.deepgram.listen.v1.connect(**options) as connection:
                    self._dg_connection = connection
                    
                    # Register event handlers
                    self._dg_connection.on("open", self._on_open)
                    self._dg_connection.on("Results", self._on_message)
                    self._dg_connection.on("close", self._on_close)
                    self._dg_connection.on("error", self._on_error)
                    
                    # Start/KeepAlive logic is handled by the client automatically in v3
                    # usually via the context manager itself.
                    
                    with self._dg_lock:
                        self._connection_active = True
                    
                    logger.info("✅ Connected to Deepgram. Listening...")
                    
                    # Wait loop
                    while not self._stop_event.is_set() and self._connection_active:
                        time.sleep(1.0)
                
                # Connection closes when exiting 'with' block
                logger.info("Deepgram connection finished.")
                with self._dg_lock:
                    self._connection_active = False

            except Exception as e:
                logger.error(f"Deepgram Connection Error: {e}")
                time.sleep(5) # Backoff

def main():
    assistant = VoiceAssistant()
    try:
        assistant.run()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
