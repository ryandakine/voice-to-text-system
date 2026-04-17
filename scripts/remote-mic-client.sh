#!/usr/bin/env bash
# remote-mic-client.sh — run on YOUR LAPTOP (the remote device you're SSHing from).
#
# Exposes your laptop's microphone to the home box via a reverse SSH tunnel and
# restarts the voice typer on the home box pointing at this remote mic.
#
# Usage:
#   ./scripts/remote-mic-client.sh user@home.ip.or.hostname [extra_ssh_args...]
#
# Example:
#   ./scripts/remote-mic-client.sh ryan@home.osi-cyber.com
#   ./scripts/remote-mic-client.sh ryan@10.0.0.5 -p 2222 -i ~/.ssh/homekey
#
# How it works:
#   1. Loads pulseaudio TCP module on your laptop, listening on 127.0.0.1:4713
#      (anonymous access restricted to loopback — only SSH can forward to it).
#   2. SSH'es to home with -R 4713:127.0.0.1:4713 so the home box sees your
#      laptop's PulseAudio via its own localhost:4713.
#   3. Runs the remote-mic-server.sh script on the home box via that SSH session.
#   4. On Ctrl-C, cleanly tears down the TCP module and closes the tunnel.
#
# After setup, speak into your laptop. Text appears in whatever window has
# focus on the home box (visible through VNC/RVNC).

set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <user@home> [extra_ssh_args...]" >&2
    exit 1
fi

HOME_SSH="$1"
shift
EXTRA_SSH_ARGS=("$@")

PULSE_TCP_PORT=4713
TCP_MODULE_ID=""
REPO_REMOTE_PATH="${VOICE_TYPER_REPO:-/home/$USER/voice-to-text-system}"

log() { echo "[remote-mic-client] $*"; }

cleanup() {
    if [[ -n "$TCP_MODULE_ID" ]]; then
        log "Unloading pulseaudio TCP module (id=$TCP_MODULE_ID)..."
        pactl unload-module "$TCP_MODULE_ID" 2>/dev/null || true
    fi
    log "Done. Your mic is no longer shared."
}
trap cleanup EXIT INT TERM

command -v pactl >/dev/null || { echo "pactl not found. Install pulseaudio-utils." >&2; exit 1; }
command -v ssh >/dev/null   || { echo "ssh not found." >&2; exit 1; }

log "Loading pulseaudio TCP module on 127.0.0.1:${PULSE_TCP_PORT}..."
TCP_MODULE_ID=$(pactl load-module module-native-protocol-tcp \
    port="$PULSE_TCP_PORT" \
    auth-anonymous=1 \
    listen=127.0.0.1) || {
    echo "Failed to load pulseaudio TCP module. Already loaded? Try:" >&2
    echo "  pactl list modules | grep -A2 module-native-protocol-tcp" >&2
    exit 1
}
log "TCP module loaded (id=$TCP_MODULE_ID)."

DEFAULT_SOURCE=$(pactl get-default-source 2>/dev/null || echo "")
log "Local default input source: ${DEFAULT_SOURCE:-<unknown>}"

log "Opening SSH to $HOME_SSH with reverse tunnel (-R ${PULSE_TCP_PORT})..."
log "When the remote shell exits, the tunnel and mic sharing end automatically."
log ""

# The reverse tunnel makes the home box see our pulse at localhost:4713.
# Then we invoke the server-side setup script. If it's not present on the
# home box, bail with a clear message.
ssh -t \
    -R "127.0.0.1:${PULSE_TCP_PORT}:127.0.0.1:${PULSE_TCP_PORT}" \
    -o ExitOnForwardFailure=yes \
    -o ServerAliveInterval=30 \
    "${EXTRA_SSH_ARGS[@]}" \
    "$HOME_SSH" \
    "bash -l -c 'if [[ -x \"${REPO_REMOTE_PATH}/scripts/remote-mic-server.sh\" ]]; then \
         \"${REPO_REMOTE_PATH}/scripts/remote-mic-server.sh\" ${PULSE_TCP_PORT} ; \
     else \
         echo \"Server script not found at ${REPO_REMOTE_PATH}/scripts/remote-mic-server.sh\" ; \
         echo \"Set VOICE_TYPER_REPO env before running this client script, or update the path.\" ; \
         exit 1 ; \
     fi ; \
     echo ; echo \"Remote mic session active. Dictate into your laptop. Ctrl+C to end.\" ; \
     read -r -d \"\" _ || true'"
