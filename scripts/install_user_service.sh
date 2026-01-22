#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_SRC="$PROJECT_DIR/systemd/voice-to-text.service"
SERVICE_DST="$HOME/.config/systemd/user/voice-to-text.service"

mkdir -p "$HOME/.config/systemd/user"

if [ ! -f "$SERVICE_SRC" ]; then
  echo "Error: service file not found: $SERVICE_SRC" >&2
  exit 1
fi

cp "$SERVICE_SRC" "$SERVICE_DST"

systemctl --user daemon-reload

# Enable service to start on login (but don't force-start; user can start from GUI/tray)
systemctl --user enable voice-to-text.service

echo "Installed user service: $SERVICE_DST"
echo "Start:   systemctl --user start voice-to-text.service"
echo "Stop:    systemctl --user stop voice-to-text.service"
echo "Restart: systemctl --user restart voice-to-text.service"

echo
echo "Tip: If the service won't start due to DISPLAY, edit: $SERVICE_DST"
