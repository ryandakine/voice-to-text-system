#!/bin/bash
# Toggle between regular voice-typer and CIMCO AI assistant
# Usage: ./toggle-cimco.sh

CIMCO_PID=$(pgrep -f "cimco_assistant.py")
VOICE_TYPER_ACTIVE=$(systemctl --user is-active voice-typer 2>/dev/null)

if [ -n "$CIMCO_PID" ]; then
    # CIMCO is running - switch to voice-typer
    echo "🔄 Stopping CIMCO Assistant..."
    pkill -f cimco_assistant
    sleep 1
    echo "🎤 Starting Voice Typer..."
    systemctl --user start voice-typer
    notify-send "Voice Mode" "Switched to regular Voice Typer" 2>/dev/null
    echo "✅ Now using: Voice Typer (types what you say)"
else
    # Voice-typer is running - switch to CIMCO
    echo "🔄 Stopping Voice Typer..."
    systemctl --user stop voice-typer
    sleep 1
    echo "🤖 Starting CIMCO Assistant..."
    cd /home/ryan/voice-to-text-system
    nohup .venv/bin/python cimco_assistant.py > /tmp/cimco_assistant.log 2>&1 &
    notify-send "CIMCO Mode" "Switched to CIMCO AI Assistant" 2>/dev/null
    echo "✅ Now using: CIMCO AI (talks to inventory)"
fi
