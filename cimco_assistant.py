#!/usr/bin/env python3
"""CIMCO Conversational AI Inventory Assistant (Local Ollama Version).

A voice-enabled AI assistant for the CIMCO inventory system.
Uses LOCAL Ollama LLM for security - no data sent to cloud.

Usage:
    python cimco_assistant.py
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

# Load .env before other imports
_script_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_script_dir, ".env"))

from deepgram import DeepgramClient
from deepgram.core.events import EventType

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
SAMPLE_RATE = 16000
CHANNELS = 1
FORMAT = pyaudio.paInt16
CHUNK_SIZE = 1024

# Ollama configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

# System prompt
SYSTEM_PROMPT = """You are CIMCO, a helpful AI assistant for an industrial scrapyard inventory system.

Your job is to help workers query and update inventory using natural language.

You have access to these tools:
- search_parts(query, zone) - Search inventory
- get_part_details(part_id) - Get details on a part
- update_quantity(part_id, change) - Add/subtract stock
- get_equipment_status() - Check equipment
- get_inventory_stats() - Get summary stats

When you need to use a tool, respond ONLY with JSON:
{"tool": "tool_name", "args": {"arg1": "value1"}}

After receiving tool results, give a brief spoken response.

Be concise - workers are busy. Example:
User: "How many crusher hammers?"
You: {"tool": "search_parts", "args": {"query": "crusher hammers"}}
[After result] "We have 15 crusher hammers."
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
        try:
            self._stream = self._pa.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                input=True,
                frames_per_buffer=CHUNK_SIZE,
            )
        except Exception as exc:
            logger.error("Failed to open microphone: %s", exc)
            self._cleanup()
            return
        
        logger.info("✅ Microphone stream started")
        
        while not self._stop_event.is_set():
            try:
                data = self._stream.read(CHUNK_SIZE, exception_on_overflow=False)
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


class CimcoAssistant:
    """Main assistant class using local Ollama LLM."""
    
    def __init__(self):
        self.deepgram = DeepgramClient()
        self._stop_event = threading.Event()
        self.conversation_history = []
        self._dg_connection = None
        self._dg_lock = threading.Lock()
        self._connection_active = False
        self._is_speaking = False  # Mute mic while TTS is playing
        self._mic = MicrophoneStreamer(self._send_audio, self._stop_event)
    
    def _send_audio(self, data: bytes):
        """Send audio to Deepgram."""
        # Don't send audio while speaking (prevents feedback loop)
        if self._is_speaking:
            return
        with self._dg_lock:
            conn = self._dg_connection
            active = self._connection_active
        if conn is None or not active:
            return
        try:
            conn.send_media(data)
        except Exception:
            pass
    
    def _call_ollama_sync(self, messages: list) -> str:
        """Call local Ollama LLM (synchronous)."""
        try:
            import urllib.request
            import urllib.parse
            
            data = json.dumps({
                "model": OLLAMA_MODEL,
                "messages": messages,
                "stream": False
            }).encode('utf-8')
            
            req = urllib.request.Request(
                f"{OLLAMA_BASE_URL}/api/chat",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            
            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result.get("message", {}).get("content", "")
        
        except Exception as e:
            logger.error(f"Ollama call failed: {e}")
            return "Sorry, the AI is not responding."
    
    def _extract_tool_call(self, response: str) -> Optional[dict]:
        """Extract tool call JSON from response."""
        try:
            match = re.search(r'\{[^{}]*"tool"[^{}]*\}', response)
            if match:
                return json.loads(match.group())
        except json.JSONDecodeError:
            pass
        return None
    
    def _process_query_sync(self, user_text: str) -> str:
        """Process a user query through Ollama (sync version)."""
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
            
            logger.info(f"Tool call: {tool_name}({tool_args})")
            
            # Execute tool (need to run async in sync context)
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(execute_tool(tool_name, tool_args))
            finally:
                loop.close()
            
            logger.info(f"Tool result: {result}")
            
            messages.append({"role": "assistant", "content": response})
            messages.append({
                "role": "user", 
                "content": f"Tool result: {json.dumps(result)}. Give a brief spoken response."
            })
            
            final_response = self._call_ollama_sync(messages)
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
        
        response = self._process_query_sync(transcript)
        if response:
            # Mute mic while speaking to prevent feedback
            self._is_speaking = True
            try:
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(speak(response))
                finally:
                    loop.close()
            finally:
                # Small delay before unmuting to let audio settle
                time.sleep(0.5)
                self._is_speaking = False
    
    def _on_message(self, message, *args, **kwargs):
        """Called when a message is received from Deepgram."""
        try:
            if hasattr(message, 'channel') and hasattr(message.channel, 'alternatives'):
                alternatives = message.channel.alternatives
                if alternatives and len(alternatives) > 0:
                    transcript = alternatives[0].transcript
                    if transcript and transcript.strip():
                        speech_final = getattr(message, 'speech_final', False)
                        if speech_final:
                            logger.info(f"🎤 Heard: {transcript}")
                            threading.Thread(
                                target=self._handle_transcript,
                                args=(transcript,),
                                daemon=True
                            ).start()
        except Exception as e:
            logger.debug(f"Error processing message: {e}")
    
    def _on_error(self, error, *args, **kwargs):
        logger.error(f"Deepgram error: {error}")
        with self._dg_lock:
            self._connection_active = False
    
    def _on_close(self, *args, **kwargs):
        logger.info("Deepgram connection closed")
        with self._dg_lock:
            self._connection_active = False
    
    def _on_open(self, *args, **kwargs):
        logger.info("Deepgram connection opened")
    
    def run(self):
        """Main run loop."""
        logger.info("=" * 50)
        logger.info("CIMCO AI Assistant (Local Ollama)")
        logger.info(f"Model: {OLLAMA_MODEL}")
        logger.info("=" * 50)
        logger.info("Speak to interact with inventory.")
        logger.info("Press Ctrl+C to exit.")
        
        # Verify Ollama
        try:
            import urllib.request
            with urllib.request.urlopen(f"{OLLAMA_BASE_URL}/api/tags", timeout=5) as resp:
                if resp.status != 200:
                    logger.error("Ollama not responding!")
                    return
            logger.info("✅ Ollama connected")
        except Exception as e:
            logger.error(f"Cannot connect to Ollama: {e}")
            return
        
        # Start microphone thread
        self._mic.start()
        
        # Deepgram streaming
        try:
            with self.deepgram.listen.v1.connect(
                model="nova-2",
                language="en-US",
                smart_format=True,
                punctuate=True,
                encoding="linear16",
                channels=CHANNELS,
                sample_rate=SAMPLE_RATE,
                interim_results=True,
                utterance_end_ms="3000",
                vad_events=True,
            ) as connection:
                
                # Register handlers
                connection.on(EventType.OPEN, self._on_open)
                connection.on(EventType.MESSAGE, self._on_message)
                connection.on(EventType.ERROR, self._on_error)
                connection.on(EventType.CLOSE, self._on_close)
                
                with self._dg_lock:
                    self._dg_connection = connection
                    self._connection_active = True
                
                # Start listening
                connection.start_listening()
                
                logger.info("✅ Connected to Deepgram - listening...")
                logger.info("")
                logger.info("🎤 Say: 'How many parts do we have?'")
                logger.info("")
                
                # Keep connection alive - mic thread sends audio
                while not self._stop_event.is_set() and self._connection_active:
                    try:
                        time.sleep(1.0)
                    except KeyboardInterrupt:
                        break
                
                with self._dg_lock:
                    self._connection_active = False
                    self._dg_connection = None
        
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        except Exception as e:
            logger.error(f"Deepgram error: {e}")
        finally:
            self._stop_event.set()
            logger.info("Cleanup complete")
    
    def stop(self):
        self._stop_event.set()


def main():
    assistant = CimcoAssistant()
    try:
        assistant.run()
    except KeyboardInterrupt:
        assistant.stop()


if __name__ == "__main__":
    main()
