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

# Import the unified entrypoint and run it in push-to-talk mode
from src.main import main

if __name__ == "__main__":
    print("Starting Voice-to-Text System (Push-to-Talk mode)...")
    # Ensure we start in PTT mode even if other defaults/config exist
    if "--mode" not in sys.argv:
        sys.argv.extend(["--mode", "ptt"])
    sys.exit(main())
