#!/usr/bin/env bash
# Voice-to-Text installer.
# Idempotent: safe to re-run. Installs system deps, Python venv, config.

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'
log()  { echo -e "${GREEN}[install]${NC} $*"; }
warn() { echo -e "${YELLOW}[install]${NC} $*"; }

REPO_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
cd "$REPO_DIR"

# --- 1. System dependencies -------------------------------------------------

log "Installing system packages (sudo apt)..."
SYSTEM_DEPS=(
    python3-venv
    python3-pip
    python3-dev
    portaudio19-dev
    python3-pyaudio
    xdotool
    xclip
    pulseaudio-utils
    libgirepository1.0-dev
    libcairo2-dev
    gir1.2-gtk-3.0
    libnotify-bin            # for notify-send (voice command help display)
    ffmpeg
)
if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -qq
    sudo apt-get install -y "${SYSTEM_DEPS[@]}"
else
    warn "apt-get not found — install these manually: ${SYSTEM_DEPS[*]}"
fi

# --- 2. Python venv ---------------------------------------------------------

if [[ ! -d .venv ]]; then
    log "Creating Python venv at .venv/"
    python3 -m venv .venv
else
    log "Python venv already exists at .venv/"
fi

log "Installing Python requirements (this can take a few minutes for faster-whisper + torch)..."
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

# --- 3. Config files --------------------------------------------------------

CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/voice-to-text"
CONFIG_FILE="$CONFIG_DIR/config.ini"
STATE_DIR="$HOME/.voice_typer"
PROVIDER_FILE="$STATE_DIR/provider.txt"

mkdir -p "$CONFIG_DIR" "$STATE_DIR"

# Auto-detect GPU so the default config matches the host.
#   nvidia-smi present + returns 0 → assume CUDA works, keep small.en + cuda
#   otherwise → switch to CPU-friendly defaults (base.en + cpu, int8 compute)
DETECTED_DEVICE="cuda"
DETECTED_MODEL="small.en"
if ! command -v nvidia-smi >/dev/null 2>&1 || ! nvidia-smi >/dev/null 2>&1; then
    DETECTED_DEVICE="cpu"
    DETECTED_MODEL="base.en"
    log "No NVIDIA GPU detected — defaulting to device=cpu, model=base.en."
    log "(You can change these in $CONFIG_FILE after install.)"
else
    log "NVIDIA GPU detected — defaulting to device=cuda, model=small.en."
fi

if [[ ! -f "$CONFIG_FILE" ]]; then
    log "Writing default config to $CONFIG_FILE"
    sed \
        -e "s/^device = cuda/device = $DETECTED_DEVICE/" \
        -e "s/^model = small.en/model = $DETECTED_MODEL/" \
        config.ini.example > "$CONFIG_FILE"
else
    log "Config already exists at $CONFIG_FILE (leaving untouched)"
fi

if [[ ! -f "$PROVIDER_FILE" ]]; then
    echo "whisper" > "$PROVIDER_FILE"
    log "Set default provider to 'whisper' ($PROVIDER_FILE)"
else
    log "Provider already set to '$(cat "$PROVIDER_FILE")' ($PROVIDER_FILE)"
fi

# --- 4. Render .desktop files with actual paths -----------------------------

APPS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$APPS_DIR"

for tmpl in "$REPO_DIR"/*.desktop; do
    [[ -e "$tmpl" ]] || continue
    name=$(basename "$tmpl")
    dest="$APPS_DIR/$name"
    sed \
        -e "s|@REPO_DIR@|$REPO_DIR|g" \
        -e "s|@HOME@|$HOME|g" \
        "$tmpl" > "$dest"
    chmod +x "$dest" 2>/dev/null || true
done
log "Installed .desktop files → $APPS_DIR"

# --- 5. Make launchers executable -------------------------------------------

chmod +x install.sh \
    run_voice_typer.sh \
    toggle-voice-typer.sh \
    voice-control.sh \
    start.sh \
    start-voice-typer.sh \
    start-voice-to-text.sh \
    scripts/remote-mic-client.sh \
    scripts/remote-mic-server.sh \
    scripts/remote-mic-teardown.sh 2>/dev/null || true

# --- 6. Done ----------------------------------------------------------------

echo ""
echo -e "${GREEN}Install complete.${NC}"
echo ""
echo "Quick start:"
echo "  ./run_voice_typer.sh       # start the voice typer"
echo "  Hold Alt to talk, release to transcribe. F8 to toggle continuous mode."
echo ""
echo "Config:    $CONFIG_FILE"
echo "Provider:  $PROVIDER_FILE (currently: $(cat "$PROVIDER_FILE"))"
echo ""
echo "First run will download the faster-whisper small.en model (~250 MB) and"
echo "Silero VAD (~2 MB). After that, everything runs offline."
