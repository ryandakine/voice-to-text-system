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

start_voice_typer() {
    echo "[$(date)] Starting Deepgram Voice Typer..." >> "$LOG_FILE"

    cd "$SCRIPT_DIR"

    # Use the same virtualenv as the existing system
    "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/voice_typer.py" \
        >> "$LOG_FILE" 2>&1

    echo "[$(date)] Deepgram Voice Typer stopped with exit code: $?" >> "$LOG_FILE"
}

# Keep the service running (restart if it crashes)
while true; do
    start_voice_typer
    echo "[$(date)] Restarting Deepgram Voice Typer in 10 seconds..." >> "$LOG_FILE"
    sleep 10
done
