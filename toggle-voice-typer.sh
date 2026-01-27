#!/bin/bash
# Toggle Voice Typer (Deepgram) on/off - WITH LOCK FILE

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
LOCK_FILE="$SCRIPT_DIR/voice_typer.lock"

# Check if running - use lock file and pgrep
if [ -f "$LOCK_FILE" ] || pgrep -f "python.*voice_typer.py" > /dev/null 2>&1; then
    # STOP - Kill all instances and remove lock
    pkill -f "python.*voice_typer.py" 2>/dev/null
    pkill -f "python.*voice_typer_tray.py" 2>/dev/null
    rm -f "$LOCK_FILE"
    notify-send -i audio-input-microphone "Voice Typer" "🔴 STOPPED" 2>/dev/null || true
else
    # START - Launch one instance with lock
    cd "$SCRIPT_DIR"
    touch "$LOCK_FILE"
    nohup "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/voice_typer.py" > "$SCRIPT_DIR/voice_typer.log" 2>&1 &
    nohup "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/voice_typer_tray.py" > /dev/null 2>&1 &
    notify-send -i audio-input-microphone "Voice Typer" "🟢 STARTED" 2>/dev/null || true
fi
