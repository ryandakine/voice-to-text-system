#!/bin/bash
# Toggle Voice Typer on/off - WITH LOCK FILE
# Reads provider from ~/.voice_typer/provider.txt to select backend:
#   "deepgram" → voice_typer_v1.py (Deepgram Nova-2 streaming, low latency)
#   "granite"  → voice_typer.py    (IBM Granite 4.0 1B local, higher latency)

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
LOCK_FILE="$SCRIPT_DIR/voice_typer.lock"
PROVIDER_FILE="$HOME/.voice_typer/provider.txt"

# Read provider (default to deepgram)
PROVIDER="deepgram"
if [ -f "$PROVIDER_FILE" ]; then
    PROVIDER="$(cat "$PROVIDER_FILE" | tr -d '[:space:]')"
fi

# Select the right script based on provider
if [ "$PROVIDER" = "granite" ]; then
    TYPER_SCRIPT="$SCRIPT_DIR/voice_typer.py"
elif [ "$PROVIDER" = "whisper" ]; then
    TYPER_SCRIPT="$SCRIPT_DIR/voice_typer_whisper.py"
else
    TYPER_SCRIPT="$SCRIPT_DIR/voice_typer_v1.py"
fi

# Check if running - use lock file and pgrep (Codex fix #1: include whisper in pattern)
if [ -f "$LOCK_FILE" ] || pgrep -f "python.*voice_typer(_v1|_whisper)?.py" > /dev/null 2>&1; then
    # STOP - Kill all instances and remove lock
    pkill -f "python.*voice_typer(_v1|_whisper)?.py" 2>/dev/null
    pkill -f "python.*voice_typer_tray.py" 2>/dev/null
    rm -f "$LOCK_FILE"
    notify-send -i audio-input-microphone "Voice Typer" "🔴 STOPPED" 2>/dev/null || true
else
    # START - Launch one instance with lock
    cd "$SCRIPT_DIR"
    touch "$LOCK_FILE"
    nohup "$SCRIPT_DIR/.venv/bin/python" "$TYPER_SCRIPT" > "$SCRIPT_DIR/voice_typer.log" 2>&1 &
    nohup "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/voice_typer_tray.py" > /dev/null 2>&1 &
    notify-send -i audio-input-microphone "Voice Typer" "🟢 STARTED ($PROVIDER)" 2>/dev/null || true
fi
