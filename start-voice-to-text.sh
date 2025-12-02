#!/bin/bash
# Voice-to-Text Push-to-Talk Startup Script

# Wait a bit for the desktop to fully load
sleep 5

# Set up logging
# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/voice-to-text-$(date +%Y%m%d).log"

# Function to start the voice-to-text system
start_voice_to_text() {
    echo "[$(date)] Starting Voice-to-Text Push-to-Talk System..." >> "$LOG_FILE"
    
    cd "$SCRIPT_DIR"
    
    # Activate virtual environment and run the application
    "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/start_push_to_talk.py" \
        >> "$LOG_FILE" 2>&1
    
    # If it crashes, log it
    echo "[$(date)] Voice-to-Text system stopped with exit code: $?" >> "$LOG_FILE"
}

# Keep the service running (restart if it crashes)
while true; do
    start_voice_to_text
    
    # Wait 10 seconds before restarting if it crashed
    echo "[$(date)] Restarting in 10 seconds..." >> "$LOG_FILE"
    sleep 10
done
