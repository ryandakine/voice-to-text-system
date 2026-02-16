#!/bin/bash
# Send control signals to voice_typer.py
# Usage: ./control-voice-typer.sh [toggle|ptt|openclaw]

ACTION=${1:-toggle}

# Find PID: Check lock file first, then fallback to pgrep
if [ -f "/tmp/voice_typer.pid" ]; then
    PID=$(cat "/tmp/voice_typer.pid")
    # Verify process actually exists
    if ! kill -0 "$PID" 2>/dev/null; then
        PID=""
    fi
fi

# Fallback
if [ -z "$PID" ]; then
    PID=$(pgrep -n -f "python.*voice_typer.py")
fi

if [ -z "$PID" ]; then
    notify-send -u critical "Voice Typer" "⚠️ Not running!"
    exit 1
fi

if [ "$ACTION" == "toggle" ]; then
    kill -SIGUSR1 "$PID"
    notify-send -t 1000 -i audio-input-microphone "Voice Typer" "🔄 Toggled Listening"
elif [ "$ACTION" == "ptt" ]; then
    kill -SIGUSR2 "$PID"
elif [ "$ACTION" == "openclaw" ]; then
    kill -SIGRTMIN "$PID"
    notify-send -t 1000 -i audio-input-microphone "Voice Typer" "🦞 Toggled OpenClaw Mode"
fi
