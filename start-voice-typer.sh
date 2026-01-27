#!/bin/bash
# Deepgram Voice Typer Startup Script

# Ensure GUI env vars exist when started via nohup / autostart
export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"

# Wait a bit for the desktop to fully load
sleep 5

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/voice-typer-$(date +%Y%m%d).log"

# Check if already running via our smart toggle script logic
# Instead of an infinite loop that ignores existing instances, we delegate to the robust toggle script.

# Execute the robust toggle script (which handles singletons and tray icons)
exec "$SCRIPT_DIR/toggle-voice-typer.sh"
