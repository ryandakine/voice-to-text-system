# Voice-to-Text for Linux

Local-first voice dictation for Linux. Hold **Alt** to talk, release to transcribe. Text types into whatever app has focus.

Runs [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (CTranslate2) locally on your GPU or CPU with [Silero VAD](https://github.com/snakers4/silero-vad) for neural silence detection. No cloud, no API keys, no per-minute cost. Cloud (Deepgram) and alternate local (IBM Granite) backends are optional.

<!-- Demo GIF placeholder — record with peek (sudo apt install peek) and drop at docs/demo.gif -->


## Why

Linux has no good first-party dictation story. Nerd-dictation, raw whisper wrappers, cloud-only tools — each has gaps. This one runs entirely on your machine, has no API keys, and is fast enough to type in real time on a mid-range GPU. Designed for devs who SSH/VNC into their workstation and want dictation that doesn't leak audio to a third party.

- ~150-300ms transcription for a 2-second utterance on an RTX GPU
- Silero neural VAD — no RMS-threshold hallucinations
- Auto-downgrade `small.en → base.en → tiny.en` when the model can't keep up
- Smart text insertion: clipboard paste for long text, keystroke for short, Ctrl+Shift+V in terminals
- Remote-mic mode: dictate from your laptop into a remote box over SSH

## Quickstart

```bash
git clone https://github.com/ryandakine/voice-to-text-system.git
cd voice-to-text-system
./install.sh
./run_voice_typer.sh
```

Then hold **Alt** and speak. Release. Text types into whatever has focus.

First run downloads `small.en` (~250 MB) and Silero VAD (~2 MB). After that, fully offline.

`install.sh` installs system deps (`xdotool`, `xclip`, `portaudio19-dev`, `pulseaudio-utils`, `ffmpeg`), creates a venv, writes `~/.config/voice-to-text/config.ini`, and auto-detects GPU (falls back to `base.en` on CPU).

### Manual install

```bash
sudo apt install xdotool xclip portaudio19-dev python3-pyaudio pulseaudio-utils ffmpeg
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
mkdir -p ~/.config/voice-to-text ~/.voice_typer
cp config.ini.example ~/.config/voice-to-text/config.ini
echo whisper > ~/.voice_typer/provider.txt
./run_voice_typer.sh
```

## Usage

Listening is **on by default**. Speak — text types into the focused app.

### Pause / resume

| Want to... | Do this |
|-----------|---------|
| Quick pause (phone call, thinking) | Hardware mic mute, or left-click the tray icon |
| Resume | Unmute / click tray |
| Hands-free pause | Say **"computer stop listening"** |
| Resume from voice-pause | **Hold Alt** and say **"computer start listening"** |

### Hotkeys

- **Alt (hold)** — push-to-talk. Captures while held, transcribes on release. Works even when continuous listening is paused.
- **F8** — toggle continuous listening. Some WMs grab F8 before the app sees it; if so, use the tray or voice command.
- **Esc** — emergency stop.

### Voice commands

Wake phrases: `computer`, `hey computer`, `ok computer`, `okay computer`.

- `stop listening` — pause
- `start listening` — resume (must be held with Alt since capture is paused)
- `scratch that` / `clear that` / `delete that` — Ctrl+Z the last dictation
- `help` / `what can i say` — desktop notification with the cheatsheet

### Visual feedback

Corner overlay (bottom-right by default):

- **Yellow spinner** — model loading
- **Low-alpha green ring** — listening, no speech
- **Green pulse** — speaking now
- **Blue slow pulse** — transcribing
- **Red** — error

Audio cues play on utterance start/end. Disable with `audio_cues = false` in config.

## How it works

```
 [mic] --PyAudio (1024-sample chunks)-->
        |
        v
 [Silero VAD] --speech probability--> [utterance buffer]
        |                                    |
        |        (448ms of silence ends utterance)
        v                                    v
 [faster-whisper small.en on GPU] --> [text] --> [text_inserter] --> [your app]
                                                   ├─ clipboard paste (long text)
                                                   └─ keystroke type (short, fallback)
```

Three separable concerns: VAD, transcription, text insertion. Each is pluggable. Entry point: [`voice_typer_whisper.py`](voice_typer_whisper.py).

## Providers

```bash
echo whisper  > ~/.voice_typer/provider.txt   # default, local, free
echo granite  > ~/.voice_typer/provider.txt   # IBM Granite 4.0 1B, local, free
echo deepgram > ~/.voice_typer/provider.txt   # Deepgram Nova-2, cloud, needs DEEPGRAM_API_KEY
./toggle-voice-typer.sh
```

| Provider   | Runtime                          | Latency    | Cost        | Offline |
|------------|----------------------------------|------------|-------------|---------|
| `whisper`  | faster-whisper + Silero VAD      | ~200-400ms | Free        | Yes     |
| `granite`  | IBM Granite 4.0 1B Speech        | ~600ms     | Free        | Yes     |
| `deepgram` | Nova-2 WebSocket streaming       | ~200-300ms | ~$0.004/min | No      |

## Configuration

Edit `~/.config/voice-to-text/config.ini`. Key Whisper settings:

```ini
[Whisper]
model = small.en             ; sweet spot; use base.en if OOM, tiny.en on CPU
device = cuda                ; cuda or cpu
auto_downgrade = true        ; step down model automatically when slow
vad_threshold = 0.2          ; Silero cutoff — lower = more sensitive
vad_silence_ms = 448         ; end-of-utterance silence window
audio_cues = true            ; set to false to silence the listen-start/end beeps
```

Full reference in [`config.ini.example`](config.ini.example).

## Remote-mic over SSH

SSH'd or VNC'd into a remote Linux box and want to dictate from your laptop's mic:

```bash
# On your laptop:
./scripts/remote-mic-client.sh ryan@remote.host
```

Reverse SSH tunnel exposes your mic to the remote box and restarts the typer there pointing at it. `Ctrl+C` when done. Teardown on the remote: `./scripts/remote-mic-teardown.sh`.

See [`scripts/README-remote-mic.md`](scripts/README-remote-mic.md) for architecture and manual fallback.

## Troubleshooting

**Nothing types when I release Alt.** `xdotool` missing or X11/Wayland permissions. Run `xdotool type "test"` — if that fails, your session can't accept synthetic input. On Wayland, switch to X11 or use the clipboard fallback (`Ctrl+Shift+V` in terminals is wired in).

**CUDA OOM or transcription lags.** Drop `model = base.en` (or `tiny.en`) in `~/.config/voice-to-text/config.ini`. Set `device = cpu` if you don't have a working CUDA install. With `auto_downgrade = true` the typer self-corrects when the real-time factor slips.

**F8 toggle doesn't fire.** Some keyboards/WMs grab F8 before pynput sees it. Use the tray icon left-click, or the `computer stop/start listening` voice commands. Alt push-to-talk always works regardless.

## System requirements

- Linux (tested on Linux Mint 21+, Ubuntu 22.04+; any modern distro with PulseAudio or PipeWire)
- Python 3.10+
- NVIDIA GPU with 4GB+ VRAM recommended for `small.en` real-time. CPU works with `tiny.en`/`base.en`.
- `xdotool` + `xclip` for text insertion

## Testing

```bash
.venv/bin/python -m pytest tests/ -v
```

17 tests covering VAD frame splitting, transcription mocks, auto-downgrade atomicity, text insertion, config loader.

## License

MIT — see [LICENSE](LICENSE).

## Credits

[faster-whisper](https://github.com/SYSTRAN/faster-whisper) (CTranslate2), [Silero VAD](https://github.com/snakers4/silero-vad), [PyAudio](https://people.csail.mit.edu/hubert/pyaudio/), [pynput](https://pynput.readthedocs.io/). Alternate paths via [openai/whisper](https://github.com/openai/whisper) and the [Deepgram Python SDK](https://github.com/deepgram/deepgram-python-sdk).
