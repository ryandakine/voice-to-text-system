"""
Deepgram-based transcription service for the existing Voice-to-Text app.

This plugs into the same TranscriptionService interface as the Whisper-based
SpeechProcessor, but sends the recorded WAV file to Deepgram's API instead.

Intended usage: swap this in when you want Deepgram + push-to-talk
(Alt-hold) semantics using the existing AudioManager and TextInserter.
"""

import os
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from deepgram import DeepgramClient

from .interfaces import TranscriptionService
from .utils.logger import logger


class DeepgramProcessor(TranscriptionService):
    """TranscriptionService implementation backed by Deepgram Nova-2.

    This is designed for *pre-recorded* audio: the existing app records
    a short WAV file when you hold Alt, then we send that file to Deepgram
    and return the transcript.
    """

    def __init__(self, model: str = "nova-2", language: str = "en-US") -> None:
        load_dotenv()

        api_key = os.getenv("DEEPGRAM_API_KEY") or os.getenv("DEEPGRAM_TOKEN")
        if not api_key:
            logger.error(
                "DeepgramProcessor: DEEPGRAM_API_KEY (or DEEPGRAM_TOKEN) is not set. "
                "Create a .env file with DEEPGRAM_API_KEY=... or export it in your shell."
            )

        # The official SDK reads DEEPGRAM_API_KEY / DEEPGRAM_TOKEN from env vars.
        # Make sure one of them is populated so DeepgramClient() works even if
        # we only loaded from .env above.
        if api_key and not os.getenv("DEEPGRAM_API_KEY"):
            os.environ["DEEPGRAM_API_KEY"] = api_key

        self._client = DeepgramClient()
        self.model = model
        self.language = language

        logger.info(f"DeepgramProcessor initialized (model={self.model}, language={self.language})")

    def load_model(self, model_name: Optional[str] = None) -> bool:
        """No-op for Deepgram; kept for interface compatibility.

        For Deepgram, there is no local model to load. We just remember
        the model name to send with each request.
        """
        if model_name:
            self.model = model_name
            logger.info(f"DeepgramProcessor model updated to: {self.model}")
        return True

    def transcribe_audio(self, audio_file: str) -> Optional[str]:
        """Send a WAV file to Deepgram and return the transcript string."""
        path = Path(audio_file)
        if not path.exists():
            logger.error(f"DeepgramProcessor: audio file not found: {audio_file}")
            return None

        try:
            logger.info(f"DeepgramProcessor: sending '{audio_file}' to Deepgram (model={self.model})")
            started = time.time()

            with path.open("rb") as f:
                audio_bytes = f.read()

            response = self._client.listen.v1.media.transcribe_file(
                request=audio_bytes,
                model=self.model,
                language=self.language,
                smart_format=True,
            )

            elapsed = time.time() - started
            logger.log_audio_event(
                "DEEPGRAM_TRANSCRIPTION_COMPLETED",
                f"duration={elapsed:.2f}s, bytes={len(audio_bytes)}",
            )

            try:
                transcript = response.results.channels[0].alternatives[0].transcript.strip()
            except Exception as exc:  # pragma: no cover - depends on SDK schema
                logger.error(f"DeepgramProcessor: unexpected response structure: {exc}")
                logger.debug("Raw Deepgram response: %s", response)
                return None

            if not transcript:
                logger.info("DeepgramProcessor: empty transcript returned")
                return None

            logger.info("DeepgramProcessor: transcription successful (len=%d)", len(transcript))
            return transcript

        except Exception as exc:  # pragma: no cover - network / SDK dependent
            logger.error(f"DeepgramProcessor: transcription failed: {exc}")
            return None
