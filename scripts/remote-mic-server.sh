#!/usr/bin/env bash
# remote-mic-server.sh — run on the HOME BOX (the machine that runs voice_typer).
#
# Picks up the PulseAudio server tunneled from a remote laptop (via SSH -R)
# and restarts voice_typer_whisper.py pointing at that tunneled source, so
# your laptop mic drives the home box's transcription.
#
# Invoked automatically by scripts/remote-mic-client.sh on the laptop, but
# you can also run it manually after setting up the tunnel yourself.
#
# Usage:
#   ./scripts/remote-mic-server.sh [pulse_tcp_port]
#
# Default port: 4713.

set -euo pipefail

PULSE_TCP_PORT="${1:-4713}"
REMOTE_PULSE="tcp:127.0.0.1:${PULSE_TCP_PORT}"
REPO="${VOICE_TYPER_REPO:-$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)}"
LAUNCHER="${REPO}/run_voice_typer.sh"
VENV_PY="${REPO}/.venv/bin/python"
SCRIPT="${REPO}/voice_typer_whisper.py"

STATE_DIR="${HOME}/.voice_typer"
STATE_PROVIDER="${STATE_DIR}/provider.txt"
STATE_REMOTE="${STATE_DIR}/remote-mic.state"

log() { echo "[remote-mic-server] $*"; }

mkdir -p "$STATE_DIR"

# --- Sanity checks ---------------------------------------------------------

command -v pactl >/dev/null || { log "ERROR: pactl not found."; exit 1; }
[[ -f "$SCRIPT"  ]] || { log "ERROR: voice typer script not found at $SCRIPT"; exit 1; }
[[ -x "$VENV_PY" ]] || { log "ERROR: venv python not found at $VENV_PY"; exit 1; }

# Probe the tunneled pulse server. If the tunnel isn't up, bail early.
if ! PULSE_SERVER="$REMOTE_PULSE" pactl info >/dev/null 2>&1; then
    log "ERROR: Cannot reach remote PulseAudio at $REMOTE_PULSE."
    log "Is the SSH -R tunnel active? See scripts/remote-mic-client.sh."
    exit 1
fi
log "Remote PulseAudio reachable at $REMOTE_PULSE."

# --- Pick a remote input source -------------------------------------------

REMOTE_SOURCE=$(PULSE_SERVER="$REMOTE_PULSE" pactl get-default-source 2>/dev/null || echo "")
if [[ -z "$REMOTE_SOURCE" ]]; then
    # Fall back to the first non-monitor source
    REMOTE_SOURCE=$(PULSE_SERVER="$REMOTE_PULSE" pactl list short sources 2>/dev/null \
        | awk '!/\.monitor\t/ {print $2; exit}')
fi
[[ -n "$REMOTE_SOURCE" ]] || { log "ERROR: No input source found on remote pulse."; exit 1; }
log "Using remote source: $REMOTE_SOURCE"

# --- Kill the currently running local voice typer -------------------------

if pgrep -f voice_typer_whisper.py >/dev/null; then
    log "Stopping local voice_typer_whisper.py..."
    pkill -f voice_typer_whisper.py || true
    sleep 3
fi

# --- Launch voice typer against the remote pulse server -------------------

# Persist state so teardown can restore cleanly.
PREV_PROVIDER=$(cat "$STATE_PROVIDER" 2>/dev/null || echo "whisper")
echo "whisper" > "$STATE_PROVIDER"   # make sure whisper is the active provider
{
    echo "PREV_PROVIDER=$PREV_PROVIDER"
    echo "PULSE_TCP_PORT=$PULSE_TCP_PORT"
    echo "STARTED_AT=$(date -Iseconds)"
} > "$STATE_REMOTE"

log "Launching voice_typer_whisper.py with PULSE_SERVER=$REMOTE_PULSE..."
LOG_FILE="${REPO}/voice_typer.log"
(
    cd "$REPO"
    PULSE_SERVER="$REMOTE_PULSE" \
    PULSE_SOURCE="$REMOTE_SOURCE" \
    nohup "$VENV_PY" "$SCRIPT" >> "$LOG_FILE" 2>&1 &
    echo $! > "${STATE_DIR}/remote-mic.pid"
)
sleep 2

if kill -0 "$(cat "${STATE_DIR}/remote-mic.pid")" 2>/dev/null; then
    log "voice_typer running against remote mic (pid=$(cat "${STATE_DIR}/remote-mic.pid"))."
    log "Log: $LOG_FILE"
    log "Dictate on your laptop. Text appears on this machine where the cursor is."
    log "End the SSH session (Ctrl+C on the laptop) to tear down and restore local mic."
else
    log "ERROR: voice_typer exited immediately. See $LOG_FILE."
    exit 1
fi
