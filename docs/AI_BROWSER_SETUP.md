# Linux-Native AI Browser Agent Fork Guide

This document describes how to produce a private fork of [`browser-use`](https://github.com/browser-use/browser-use) that runs entirely on Ubuntu/Debian without containers. All changes are MIT-licensed with optional GPLv3 redistribution notes.

## 1. Fork and Clone Workflow

```bash
# Create a fork on GitHub, then configure remotes locally
mkdir -p ~/ai-browser && cd ~/ai-browser
GitHubUser="your-github-username"
git clone https://github.com/$GitHubUser/browser-use.git
cd browser-use
# add upstream reference
git remote add upstream https://github.com/browser-use/browser-use.git
```

## 2. File Overview

Key files introduced by this customization:

- `browser_privacy_agent/` – Python package powering the Linux-native agent
  - `config.py` – environment-driven configuration loader
  - `llm_loader.py` – local Qwen uncensored model loader (4-bit CUDA only)
  - `prompting.py` – Jinja2 templates with `<think>` reasoning tags
  - `playwright_wrapper.py` – stealth Playwright helpers with fingerprint evasion
  - `validator_rotator.py` – cross-model hallucination checks and alerts
  - `gui.py` – optional Gradio UI
  - `main.py` – demo entry point (`python -m browser_privacy_agent.main ...`)
- `install.sh` – bash installer (apt + venv) with Playwright Chromium setup
- `.env.example` – configuration template for privacy settings
- `ai-browser.service` – reference systemd unit for daemonizing the agent
- `docs/AI_BROWSER_SETUP.md` – this guide

## 3. Installation Script

Run the installer with sudo to provision dependencies and systemd service:

```bash
sudo ./install.sh
```

The script installs system packages (Python headers, Playwright libs), creates a virtual environment under `.venv`, installs Python dependencies (`playwright`, `transformers`, `accelerate`, `bitsandbytes`, `gradio`, `nginx`, `python-dotenv`, `jinja2`), and registers `ai-browser.service`.

## 4. Systemd Service

The generated `/etc/systemd/system/ai-browser.service` runs the agent as a background daemon on boot. Control it via:

```bash
sudo systemctl enable ai-browser.service
sudo systemctl start ai-browser.service
sudo systemctl status ai-browser.service
```

Edit `ExecStart` or environment variables in `.env` to customize behaviour.

## 5. Usage

1. Customize `.env` or copy `.env.example`.
2. Start the daemon (`systemctl start ai-browser.service`) or run manually:

   ```bash
   source .venv/bin/activate
   python -m browser_privacy_agent.main --task "Scrape and summarize uncensored content from example.com undetected" --url https://example.com
   ```

3. Optional GUI: set `AI_BROWSER_ENABLE_GUI=1` and run `python -m browser_privacy_agent.gui`. Access behind nginx reverse proxy at `http://127.0.0.1:8080` (internally proxies to Gradio `localhost:7860`).

## 6. Git Commit & Push

```bash
git status
git add browser_privacy_agent install.sh ai-browser.service .env.example docs/AI_BROWSER_SETUP.md
git commit -m "Add Linux-native privacy browser agent"
git push origin main  # or your active branch
```

When preparing a pull request, include MIT notice and optional GPLv3 sharing note. Ensure no telemetry or cloud calls are enabled unless explicitly configured via `.env`.
