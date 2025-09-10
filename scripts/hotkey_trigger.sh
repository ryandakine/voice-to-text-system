#!/bin/bash

# Hotkey trigger script for voice-to-text system
# This script is called by xbindkeys when the hotkey is pressed

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Send SIGUSR1 to the main application's PID if it exists
PID_FILE="$PROJECT_DIR/tmp/voice-to-text.pid"
if [ -f "$PID_FILE" ]; then
  PID=$(cat "$PID_FILE")
  if kill -0 "$PID" 2>/dev/null; then
    kill -USR1 "$PID"
    exit 0
  fi
fi

# If we get here, the PID file is missing or the process isn't running
# Optionally, you could start the app or log an error here.
exit 1

