#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$REPO_DIR/.venv"

if [[ $EUID -ne 0 ]]; then
  echo "Please run install.sh with sudo to install system dependencies."
  exit 1
fi

apt-get update
apt-get install -y python3-dev python3-pip git libnss3 libatk-bridge2.0-0 libdrm2 libgbm1 libasound2

sudo -u ${SUDO_USER:-$USER} python3 -m venv "$VENV_DIR"
sudo -u ${SUDO_USER:-$USER} "$VENV_DIR/bin/pip" install --upgrade pip
sudo -u ${SUDO_USER:-$USER} "$VENV_DIR/bin/pip" install playwright transformers accelerate bitsandbytes gradio nginx python-dotenv jinja2
sudo -u ${SUDO_USER:-$USER} "$VENV_DIR/bin/playwright" install --with-deps chromium

cat <<SERVICE | tee /etc/systemd/system/ai-browser.service > /dev/null
[Unit]
Description=AI Privacy Browser Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${SUDO_USER:-$USER}
WorkingDirectory=$REPO_DIR
Environment=AI_BROWSER_ENV_FILE=$REPO_DIR/.env
ExecStart=$VENV_DIR/bin/python -m browser_privacy_agent.main --task "Startup monitor" --context "Boot sequence"
Restart=on-failure
RestartSec=15

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable ai-browser.service

cat <<'ENV' > "$REPO_DIR/.env"
AI_BROWSER_ENABLE_GUI=0
AI_BROWSER_ENABLE_NGINX=0
AI_BROWSER_HEADLESS=1
AI_BROWSER_STEALTH=1
AI_BROWSER_MAX_RETRIES=3
AI_BROWSER_SMTP_HOST=
AI_BROWSER_SMTP_PORT=587
AI_BROWSER_SMTP_USERNAME=
AI_BROWSER_SMTP_PASSWORD=
AI_BROWSER_SMTP_SENDER=
AI_BROWSER_SMTP_RECIPIENT=
AI_BROWSER_VALIDATOR_1_NAME=deepseek-lite
AI_BROWSER_VALIDATOR_1_KIND=local-deepseek
AI_BROWSER_VALIDATOR_1_MODEL=deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct
AI_BROWSER_VALIDATOR_1_ENABLED=0
AI_BROWSER_VALIDATOR_1_SANITIZE=1
ENV

chown ${SUDO_USER:-$USER}:${SUDO_USER:-$USER} "$REPO_DIR/.env"

cat <<'NGINX' > /etc/nginx/sites-available/ai-browser
server {
    listen 127.0.0.1:8080;
    server_name localhost;

    location / {
        proxy_pass http://127.0.0.1:7860;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
NGINX
ln -sf /etc/nginx/sites-available/ai-browser /etc/nginx/sites-enabled/ai-browser
systemctl reload nginx || true

echo "Installation complete. Use systemctl start ai-browser.service to begin."
