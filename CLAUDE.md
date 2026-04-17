# Voice-to-Text System — AI Assistant Guide

## Project Overview

A system-wide voice-to-text application for Linux (Mint/Ubuntu). Provides global hotkey-triggered speech-to-text with universal text insertion into any application. Two transcription backends are supported and are interchangeable at startup:

- Deepgram Nova-2: real-time streaming via WebSocket, cloud-based, lowest latency
- OpenAI Whisper: local offline inference, no API cost, higher latency

Also integrates an OpenClaw AI mode (F9) that routes voice commands to GLM-5 via the OpenClaw gateway with Deepgram Aura TTS responses.

IMPORTANT: Deepgram and Whisper modes cannot run simultaneously due to audio device conflicts.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.8+ |
| STT (cloud) | Deepgram Nova-2 (deepgram-sdk>=3.0.0) — WebSocket streaming |
| STT (local) | OpenAI Whisper (openai-whisper) — local inference |
| Audio capture | PyAudio + PortAudio |
| Audio processing | numpy, soundfile, librosa |
| Hotkeys | pynput, keyboard |
| Text insertion | xdotool, pyautogui, pyperclip (multi-strategy with fallback) |
| GUI | PyGObject (GTK3), system tray |
| Health APIs | Samsung Health + Whoop (REST OAuth) |
| Config | configparser (INI in ~/.config/voice-to-text/) |
| Dashboard | Node.js Express (dashboard-server.js) |

## Repository Structure

```
src/
  main.py                  Entry point + mode selection
  application.py           Main app orchestrator
  interfaces.py            TranscriptionService abstract interface (ABC)
  deepgram_processor.py    Deepgram Nova-2 real-time streaming service
  speech_processor.py      Whisper local transcription service
  audio_manager.py         PyAudio recording abstraction
  hotkey_handler.py        Global hotkey registration
  push_to_talk_handler.py  Alt-hold push-to-talk logic
  text_insertion.py        Multi-strategy text injector
  input_strategy.py        Strategy pattern for text insertion
  voice_typer.py           Deepgram live streaming voice typer
  voice_assistant.py       Voice assistant mode
  tts_speaker.py           TTS response playback (Deepgram Aura)
  gui/                     GTK3 status window + system tray
  health_integration/      Samsung Health + Whoop connectors + HealthMonitor
  utils/                   Logging, audio utilities
agentic_terminal/          Agentic terminal integration
systemd/                   User systemd service units
scripts/                   Install script, hotkey trigger scripts
```

## Key Commands

```bash
# Deepgram Mode (Recommended)
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
sudo apt install -y xdotool python3-pyaudio portaudio19-dev
cp .env.example .env    # Add DEEPGRAM_API_KEY
./toggle-voice-typer.sh
# F8 to pause/resume, F9 for OpenClaw AI mode

# Whisper Mode (Local/Offline)
./install.sh
python3 src/main.py --mode hotkey   # F5 to record
python3 src/main.py --mode ptt      # Alt-hold push-to-talk
python3 src/main.py --mode auto     # Auto silence detection

# System service
systemctl --user enable voice-to-text.service
systemctl --user start voice-to-text.service

# Dashboard
node dashboard-server.js    # http://localhost:3456
```

## Architecture Patterns

### TranscriptionService Interface
Both Deepgram and Whisper implement the TranscriptionService abstract interface in src/interfaces.py. They are interchangeable at startup — application.py selects the implementation based on --mode flag or config.

When adding a new STT backend, implement TranscriptionService and register it in application.py. Do not add mode-specific branching outside of application.py.

### Multi-Strategy Text Insertion
text_insertion.py tries three methods in order, falling back on failure:
1. Clipboard paste (pyperclip + Ctrl+V) — fastest
2. xdotool type — for apps that block clipboard
3. Keyboard simulation (pyautogui) — last resort

Never remove a strategy — each handles apps that break the previous one.

### Config Location
All user config lives in ~/.config/voice-to-text/ (INI format). Do not hardcode paths. Default config is created on first run.

### Health Integration
src/health_integration/ connects to Samsung Health and Whoop APIs. HealthMonitor provides real-time biometric data that voice assistant mode uses to adapt response tone. Optional — degrades gracefully if APIs are unavailable.

## Environment Variables

| Variable | Description |
|----------|-------------|
| DEEPGRAM_API_KEY | Deepgram API key (required for Deepgram mode) |
| OPENCLAW_GATEWAY_URL | OpenClaw gateway URL for F9 AI mode |
| SAMSUNG_HEALTH_TOKEN | Samsung Health OAuth token (optional) |
| WHOOP_CLIENT_ID | Whoop API client ID (optional) |
| WHOOP_CLIENT_SECRET | Whoop API client secret (optional) |

## Testing

```bash
pytest tests/
python3 test_installation.py     # Verify all dependencies installed correctly
python3 test_input.py            # Test text insertion strategies
python3 test_pynput.py           # Test hotkey capture
python3 test_health_integration.py  # Test health API connections
```

Run test_installation.py first on a new machine.

## System Requirements

- Linux (Ubuntu 20.04+ or Linux Mint 20+)
- xdotool (text insertion)
- portaudio19-dev + python3-pyaudio (audio capture)
- GTK3 (GUI/tray icon)
- Working audio input device

## Important Constraints

- Deepgram and Whisper cannot run simultaneously — both claim the audio device.
- xdotool is required — without it the system falls back to clipboard-only mode.
- F9 OpenClaw AI mode requires OPENCLAW_GATEWAY_URL — falls back to standard transcription without it.
- Text insertion strategy order must not change — the fallback chain is ordered by reliability.
- Config is in ~/.config/voice-to-text/ — never hardcode paths or write config to the repo directory.
