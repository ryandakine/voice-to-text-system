#!/usr/bin/env python3
"""Push-to-talk launcher that uses Deepgram instead of Whisper.

Behavior is intentionally very close to your existing push-to-talk setup:
- Hold Alt to record via AudioManager
- Release Alt to stop
- Recorded clip is sent to Deepgram (nova-2) for transcription
- Result is inserted at cursor via TextInserter

This does NOT modify the existing Whisper-based flow; it's a separate
entrypoint you can run side-by-side for comparison.
"""

import sys
from pathlib import Path

# Add project root and src directory to Python path
project_root = Path(__file__).parent
src_path = project_root / "src"
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from src.application import VoiceToTextApp
from src.push_to_talk_handler import PushToTalkHandler
from src.input_strategy import PTTInputStrategy
from src.text_insertion import TextInserter
from src.utils.logger import logger
from src.deepgram_processor import DeepgramProcessor


def main() -> int:
    logger.info("Starting Voice-to-Text System (Push-to-Talk, Deepgram engine)...")

    transcription_service = DeepgramProcessor(model="nova-2", language="en-US")
    output_service = TextInserter()

    ptt_handler = PushToTalkHandler()
    input_strategy = PTTInputStrategy(ptt_handler)

    app = VoiceToTextApp(
        transcription_service=transcription_service,
        output_service=output_service,
        input_strategy=input_strategy,
    )

    try:
        app.start()
        return 0
    except KeyboardInterrupt:
        logger.info("Exiting (KeyboardInterrupt)...")
        app.stop()
        return 0
    except Exception as exc:
        logger.critical(f"Fatal error in Deepgram PTT launcher: {exc}")
        app.stop()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
