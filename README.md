# Voice-to-Text for Linux

A system-wide, local-first voice dictation tool for Linux. Hold **Alt** to talk, release to transcribe. Text types into whatever app has focus.

Runs [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (CTranslate2) locally on your GPU or CPU with [Silero VAD](https://github.com/snakers4/silero-vad) for neural silence detection. No cloud, no API keys, no per-minute cost. Cloud (Deepgram) and alternate local (IBM Granite) backends are optional.

![demo placeholder — record with peek: sudo apt install peek](docs/demo.gif)

## Why this exists

Linux doesn't have a great first-party dictation story. Nerd-dictation, whisper wrappers, cloud-only tools — each has gaps. This project combines:

- **Near-real-time local transcription** (~150-300ms for a 2-second utterance on an RTX GPU — faster than Deepgram streaming in many setups)
- **No silence hallucinations** (Silero neural VAD, not RMS thresholds)
- **Smart text insertion** — clipboard paste for long text, keystroke for short, app-aware paste hotkey (Ctrl+Shift+V for terminals)
- **Auto-downgrade** — when the model can't keep up, the system steps down `small.en → base.en → tiny.en` based on measured real-time factor
- **Remote-mic mode** — dictate from your laptop microphone into a home workstation over SSH reverse tunnel (great for VNC workflows)

## Install

```bash
git clone https://github.com/ryandakine/voice-to-text-system.git
cd voice-to-text-system
./install.sh
```

What `install.sh` does:

1. Installs system deps: `xdotool`, `xclip`, `portaudio19-dev`, `pulseaudio-utils`.
2. Creates a Python venv in `.venv/` and installs pip requirements.
3. Copies default config to `~/.config/voice-to-text/config.ini`.
4. Sets `~/.voice_typer/provider.txt = whisper` (the blessed default).
5. Renders `.desktop` files with your paths for launchers and tray.

### Manual install

```bash
sudo apt install xdotool xclip portaudio19-dev python3-pyaudio pulseaudio-utils

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

mkdir -p ~/.config/voice-to-text ~/.voice_typer
cp config.ini.example ~/.config/voice-to-text/config.ini
echo whisper > ~/.voice_typer/provider.txt

./run_voice_typer.sh
```

## Usage

Once running:

- **Alt (hold)** — push-to-talk. Release to transcribe.
- **F8** — toggle continuous listening on/off.
- **Esc** — emergency stop.

Start via the tray icon (`voice_typer_tray.py`) or directly:

```bash
./run_voice_typer.sh
```

## Providers

Switch backends without touching code:

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

Three separable concerns: voice activity detection, transcription, text insertion. Each is pluggable. Entry point: [`voice_typer_whisper.py`](voice_typer_whisper.py).

## System requirements

- Linux (tested on Linux Mint 21+, Ubuntu 22.04+; any modern distro with PulseAudio or PipeWire should work)
- Python 3.10+
- Recommended: NVIDIA GPU with 4GB+ VRAM for `small.en` at real-time speeds. CPU-only works with `tiny.en` or `base.en`.
- `xdotool` + `xclip` for text insertion
- PulseAudio or PipeWire for audio capture

## Testing

```bash
.venv/bin/python -m pytest tests/ -v
```

17 unit tests covering VAD frame splitting, transcription mocks, auto-downgrade atomicity, text insertion strategies, and the config loader.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Open issues are tracked in GitHub Issues.

## License

MIT — see [LICENSE](LICENSE).

## Credits

Built on [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (CTranslate2), [Silero VAD](https://github.com/snakers4/silero-vad), [PyAudio](https://people.csail.mit.edu/hubert/pyaudio/), and [pynput](https://pynput.readthedocs.io/). OpenAI Whisper alternate path via [openai/whisper](https://github.com/openai/whisper). Deepgram provider via the official [Deepgram Python SDK](https://github.com/deepgram/deepgram-python-sdk).
