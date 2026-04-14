#!/bin/bash
cd /home/ryan/voice-to-text-system

PROVIDER_FILE="$HOME/.voice_typer/provider.txt"
PROVIDER="deepgram"
if [ -f "$PROVIDER_FILE" ]; then
    PROVIDER="$(cat "$PROVIDER_FILE" | tr -d '[:space:]')"
fi

if [ "$PROVIDER" = "granite" ]; then
    SCRIPT="voice_typer.py"
elif [ "$PROVIDER" = "whisper" ]; then
    SCRIPT="voice_typer_whisper.py"
else
    SCRIPT="voice_typer_v1.py"
fi

exec /home/ryan/voice-to-text-system/.venv/bin/python -u /home/ryan/voice-to-text-system/$SCRIPT
