#!/bin/bash
# Toggle Voice Typer on/off — with lock file.
# Reads provider from ~/.voice_typer/provider.txt to select backend:
#   "whisper"  → voice_typer_whisper.py (faster-whisper + Silero VAD, local, free) [default]
#   "granite"  → voice_typer.py         (IBM Granite 4.0 1B, local, free)
#   "deepgram" → voice_typer_v1.py      (Deepgram Nova-2 streaming, cloud, paid)

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
LOCK_FILE="$SCRIPT_DIR/voice_typer.lock"
PROVIDER_FILE="$HOME/.voice_typer/provider.txt"

# Read provider (default to whisper — local, free, fast).
PROVIDER="whisper"
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
    # The HF hub re-validates the model over the network on every start and re-downloads it,
    # which stalls on slow/flaky wifi even when the model is already fully cached. Load
    # cache-only so startup is instant and offline-safe.
    # NOTE: offline mode blocks new downloads. voice_typer_whisper.py loads models from
    # download_root=~/.cache/whisper (NOT the default ~/.cache/huggingface/hub). To switch to a
    # not-yet-cached model later, pre-download it INTO that dir first, then it loads offline:
    #   .venv/bin/python -c "from faster_whisper import WhisperModel; WhisperModel('<model>', device='cpu', download_root='$HOME/.cache/whisper')"
    # (that download needs network, so run it with HF_HUB_OFFLINE unset.)
    export HF_HUB_OFFLINE=1
    touch "$LOCK_FILE"
    nohup "$SCRIPT_DIR/.venv/bin/python" "$TYPER_SCRIPT" > "$SCRIPT_DIR/voice_typer.log" 2>&1 &
    nohup "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/voice_typer_tray.py" > /dev/null 2>&1 &
    notify-send -i audio-input-microphone "Voice Typer" "🟢 STARTED ($PROVIDER)" 2>/dev/null || true
fi
