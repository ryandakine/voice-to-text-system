#!/usr/bin/env python3
"""Text-to-Speech Speaker using Deepgram Aura API.

Provides spoken responses for the CIMCO AI assistant.
"""

import os
import io
import logging
from typing import Optional

from dotenv import load_dotenv

# Load environment variables
_script_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_script_dir, ".env"))

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")

# Try importing audio playback libraries
try:
    import simpleaudio as sa
    AUDIO_BACKEND = "simpleaudio"
except ImportError:
    try:
        import pygame
        pygame.mixer.init()
        AUDIO_BACKEND = "pygame"
    except ImportError:
        AUDIO_BACKEND = "subprocess"  # Fallback to aplay/ffplay

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def speak(text: str, voice: str = "aura-asteria-en") -> bool:
    """Convert text to speech and play it through speakers.
    
    Args:
        text: The text to speak
        voice: Deepgram Aura voice model (default: aura-asteria-en)
    
    Returns:
        True if successful, False otherwise
    """
    if not text:
        return False
    
    if not DEEPGRAM_API_KEY:
        logger.error("DEEPGRAM_API_KEY not set - cannot use TTS")
        return False
    
    try:
        import httpx
        
        # Deepgram Aura TTS endpoint
        url = f"https://api.deepgram.com/v1/speak?model={voice}"
        headers = {
            "Authorization": f"Token {DEEPGRAM_API_KEY}",
            "Content-Type": "application/json"
        }
        body = {"text": text}
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=body)
            
            if response.status_code != 200:
                logger.error(f"Deepgram TTS failed: {response.status_code} - {response.text}")
                return False
            
            audio_data = response.content
            logger.info(f"Received {len(audio_data)} bytes of audio")
            
            # Play audio
            return _play_audio(audio_data)
    
    except Exception as e:
        logger.error(f"TTS error: {e}")
        return False


def _play_audio(audio_data: bytes) -> bool:
    """Play audio data through speakers."""
    try:
        if AUDIO_BACKEND == "simpleaudio":
            # Deepgram returns MP3, need to convert or use different approach
            # For now, save to temp file and use subprocess
            import tempfile
            import subprocess
            
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(audio_data)
                temp_path = f.name
            
            # Try ffplay (quiet mode)
            try:
                subprocess.run(
                    ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", temp_path],
                    check=True,
                    timeout=30
                )
            except FileNotFoundError:
                # Fallback to mpv
                subprocess.run(
                    ["mpv", "--no-video", "--really-quiet", temp_path],
                    check=True,
                    timeout=30
                )
            
            os.unlink(temp_path)
            return True
        
        elif AUDIO_BACKEND == "pygame":
            import pygame
            import tempfile
            
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(audio_data)
                temp_path = f.name
            
            pygame.mixer.music.load(temp_path)
            pygame.mixer.music.play()
            
            # Wait for playback to finish
            while pygame.mixer.music.get_busy():
                pygame.time.wait(100)
            
            os.unlink(temp_path)
            return True
        
        else:
            # Subprocess fallback
            import tempfile
            import subprocess
            
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(audio_data)
                temp_path = f.name
            
            # Try mpv first, then ffplay, then aplay
            for player in [["mpv", "--no-video", "--really-quiet"], 
                          ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"],
                          ["aplay"]]:
                try:
                    subprocess.run(player + [temp_path], check=True, timeout=30)
                    os.unlink(temp_path)
                    return True
                except (FileNotFoundError, subprocess.CalledProcessError):
                    continue
            
            os.unlink(temp_path)
            logger.error("No audio player available (tried mpv, ffplay, aplay)")
            return False
    
    except Exception as e:
        logger.error(f"Audio playback error: {e}")
        return False


def speak_sync(text: str, voice: str = "aura-asteria-en") -> bool:
    """Synchronous wrapper for speak() function."""
    import asyncio
    return asyncio.run(speak(text, voice))


# Test function
if __name__ == "__main__":
    import asyncio
    
    async def test():
        print("Testing Deepgram TTS...")
        success = await speak("Hello, this is a test of the CIMCO inventory assistant. How can I help you today?")
        print(f"TTS {'succeeded' if success else 'failed'}")
    
    asyncio.run(test())
