#!/usr/bin/env python3
"""
Launcher script for the push-to-talk voice-to-text system.
"""

import sys
import os
from pathlib import Path

# Add the src directory to the Python path
project_root = Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(src_path))

# Import and run the push-to-talk main module
from src.main_push_to_talk import main

if __name__ == "__main__":
    print("Starting Voice-to-Text System with Push-to-Talk...")
    print("Loading Whisper model (this may take a moment on first run)...")
    sys.exit(main())
