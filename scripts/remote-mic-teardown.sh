#!/usr/bin/env bash
# remote-mic-teardown.sh — run on the HOME BOX to restore local-mic operation.
#
# Kills the remote-mic voice_typer instance and restarts voice_typer against
# the local microphone. Use when the SSH tunnel drops or you want to go
# back to in-person dictation.

set -euo pipefail

REPO="${VOICE_TYPER_REPO:-$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)}"
VENV_PY="${REPO}/.venv/bin/python"
SCRIPT="${REPO}/voice_typer_whisper.py"
STATE_DIR="${HOME}/.voice_typer"
STATE_REMOTE="${STATE_DIR}/remote-mic.state"
REMOTE_PID_FILE="${STATE_DIR}/remote-mic.pid"

log() { echo "[remote-mic-teardown] $*"; }

# Kill whichever voice_typer is running (local-mic or remote-mic variant).
if [[ -f "$REMOTE_PID_FILE" ]]; then
    REMOTE_PID=$(cat "$REMOTE_PID_FILE" || echo "")
    if [[ -n "$REMOTE_PID" ]] && kill -0 "$REMOTE_PID" 2>/dev/null; then
        log "Stopping remote-mic voice_typer (pid=$REMOTE_PID)..."
        kill "$REMOTE_PID" 2>/dev/null || true
    fi
    rm -f "$REMOTE_PID_FILE"
fi
pkill -f voice_typer_whisper.py || true
sleep 2

# Restart with local mic (no PULSE_SERVER env).
log "Starting local-mic voice_typer_whisper.py..."
LOG_FILE="${REPO}/voice_typer.log"
(
    cd "$REPO"
    nohup "$VENV_PY" "$SCRIPT" >> "$LOG_FILE" 2>&1 &
)
sleep 2

if pgrep -f voice_typer_whisper.py >/dev/null; then
    log "Local voice_typer restarted. Ready for in-person dictation."
else
    log "WARNING: voice_typer did not restart. Check $LOG_FILE."
fi

rm -f "$STATE_REMOTE"
