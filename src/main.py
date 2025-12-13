"""
Main entry point for the Voice-to-Text System.
Supports both Voice Activation/Hotkey and Push-to-Talk via configuration.
"""

import sys
import argparse
import signal
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.utils.logger import logger
from src.utils.config_manager import config
from src.speech_processor import SpeechProcessor
from src.text_insertion import TextInserter
from src.hotkey_handler import HotkeyHandler
from src.push_to_talk_handler import PushToTalkHandler
from src.input_strategy import HotkeyInputStrategy, PTTInputStrategy
from src.application import VoiceToTextApp

def parse_args():
    parser = argparse.ArgumentParser(description="Voice-to-Text System")
    parser.add_argument('--mode', choices=['hotkey', 'ptt'], default=None, 
                        help="Input mode: 'hotkey' (toggle) or 'ptt' (push-to-talk)")
    return parser.parse_args()

def main():
    args = parse_args()
    
    # 1. Initialize Services
    transcription_service = SpeechProcessor()
    output_service = TextInserter()
    
    # 2. Determine Input Strategy
    # Priority: CLI Argument > Config > Default (hotkey)
    mode = args.mode
    if not mode:
        # Check config (assuming we add a 'mode' to config later, for now default to 'hotkey')
        mode = 'hotkey' 
    
    input_strategy = None
    if mode == 'ptt':
        logger.info("Starting in Push-to-Talk mode")
        ptt_handler = PushToTalkHandler()
        input_strategy = PTTInputStrategy(ptt_handler)
    else:
        logger.info("Starting in Hotkey Toggle mode")
        hotkey_handler = HotkeyHandler()
        input_strategy = HotkeyInputStrategy(hotkey_handler)
    
    # 3. Create Application
    app = VoiceToTextApp(
        transcription_service=transcription_service,
        output_service=output_service,
        input_strategy=input_strategy
    )
    
    # 4. Run Application
    try:
        app.start()
    except KeyboardInterrupt:
        logger.info("Exiting...")
        app.stop()
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        app.stop()
        sys.exit(1)

if __name__ == "__main__":
    main()
