#!/bin/bash
# Route to the configured voice typer provider.
REPO_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
cd "$REPO_DIR"

PROVIDER_FILE="$HOME/.voice_typer/provider.txt"
PROVIDER="whisper"
if [ -f "$PROVIDER_FILE" ]; then
    PROVIDER="$(cat "$PROVIDER_FILE" | tr -d '[:space:]')"
fi

if [ "$PROVIDER" = "granite" ]; then
    SCRIPT="voice_typer.py"
elif [ "$PROVIDER" = "deepgram" ]; then
    SCRIPT="voice_typer_v1.py"
else
    SCRIPT="voice_typer_whisper.py"
fi

PY="${REPO_DIR}/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"

exec "$PY" -u "${REPO_DIR}/${SCRIPT}"
