# Voice-to-Text System — AI Assistant Guide

## What this is

Local-first voice dictation for Linux. Hold **Alt** to talk, release to transcribe; text types into the focused app. **Default and required backend is local whisper (faster-whisper + Silero VAD) — no cloud STT.** Cloud (Deepgram Nova-2) and an alternate local backend (IBM Granite 4.0 1B) exist in the code as opt-in providers but are not to be enabled per user policy; treat them as legacy, not recommended.

## Entry points (verify before trusting stale docs — this repo has two generations of code)

Live path, in the last 5 commits:
- `./toggle-voice-typer.sh` — start/stop with lockfile + pkill. Reads `~/.voice_typer/provider.txt` (`whisper` default, or `granite`/`deepgram`) and launches the matching script:
  - `voice_typer_whisper.py` — blessed default. Alt PTT always works; continuous listening is off by default (F8 or tray toggles it, or say "computer start/stop listening").
  - `voice_typer.py` (granite), `voice_typer_v1.py` (deepgram, legacy/cloud) — opt-in only.
- `voice_typer_tray.py` — system tray, launched alongside.
- `history_manager.py` → SQLite at `~/.voice_typer/history.db`. `config_manager.py` → JSON at `~/.voice_typer/config.json` (shortcuts, history, export, voice-command settings). `voice_commands.py` — wake-phrase ("computer …") command processor.

Legacy path (`src/main.py`, `application.py`, `interfaces.py`, `deepgram_processor.py`, `speech_processor.py`, `hotkey_handler.py`, `push_to_talk_handler.py`, `audio_manager.py`, `health_integration/`): only reachable via `launcher.py` / `start_push_to_talk_deepgram.py`, not the toggle script (git shows these last meaningfully changed Dec 2025–Apr 2026). Treat as superseded — do not extend it for new work without checking it's actually still wired to something.

Exception — these `src/` files ARE live (imported by `voice_typer_whisper.py`), don't delete as "dead src/": `text_insertion.py` (line ~872), plus optional imports `listening_overlay.py` (overlay UI) and `partial_buffer.py` (streaming partials — this is the file the 2026-04-16 commit actually touched). Note `input_strategy.py` is NOT on the whisper path — it's imported only by the legacy Deepgram path, so it belongs with the legacy list above, not here.

F9/OpenClaw-AI-mode routing to a GLM-5 gateway exists only in the legacy/opt-in scripts (`voice_typer_v1.py`, `voice_typer.py`, `shortcuts.py`, `control-voice-typer.sh`) — not in the default whisper path.

## Config (two real locations, both live)

- `~/.config/voice-to-text/config.ini` — whisper/audio params (model, device, vad_threshold, auto_downgrade). Template: `config.ini.example`.
- `~/.voice_typer/config.json` — shortcuts, history retention, export, voice-command prefix. Written/read by `config_manager.py`; defaults created on first run.

## Key commands

```bash
./install.sh              # system deps + venv + both config dirs
./toggle-voice-typer.sh   # start/stop (provider from ~/.voice_typer/provider.txt)
./run_voice_typer.sh      # direct launch, no toggle/lock
.venv/bin/python -m pytest tests/ -v   # run `--collect-only -q` first for the current count — it drifts every commit
```

`systemd/voice-to-text.service`'s `ExecStart` points at `start_push_to_talk.py`, which does not exist in this repo — the unit is broken as committed; don't `systemctl enable` it without fixing the path first.

## Constraints

- Only one provider process runs at a time (toggle script kills prior instances before starting).
- `xdotool` required for text insertion; `src/text_insertion.py` falls back primary→secondary method (clipboard/keyboard/xdotool, configurable) — not a fixed 3-step chain.
- Config paths are fixed (`~/.config/voice-to-text/`, `~/.voice_typer/`) — don't hardcode elsewhere or write config into the repo dir.

