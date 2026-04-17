# Remote Microphone over SSH

Dictate from your laptop/phone microphone and have the text typed on your home box
(visible via VNC/RVNC). No firewall changes — everything goes through the SSH tunnel.

## Architecture

```
  [Laptop mic] --pactl--> localhost:4713 (pulse TCP)
       ^                                 |
       |                                 | SSH -R reverse tunnel
       |                                 v
       └──────── home box listens at localhost:4713
                 voice_typer_whisper.py reads from it
                 transcription types into the focused VNC window
```

## Prerequisites

- SSH access from laptop to home box.
- `pulseaudio-utils` (for `pactl`) on both machines — already default on most Linux.
- Voice typer repo cloned at `/home/ryan/voice-to-text-system` on the home box
  (or set `VOICE_TYPER_REPO` env to the actual path on both machines).
- Home box's voice typer must be using the `whisper` provider
  (`echo whisper > ~/.voice_typer/provider.txt`).

## Usage

### Start a remote-mic session

On your **laptop**:

```bash
cd /path/to/voice-to-text-system
./scripts/remote-mic-client.sh ryan@home.example.com
```

This will:
1. Expose your laptop's PulseAudio on `127.0.0.1:4713` (anonymous loopback only).
2. Open an SSH session with `-R 4713:127.0.0.1:4713` so the home box sees it.
3. Restart voice_typer on the home box pointing at the tunneled mic.
4. Hold the session open until you press `Ctrl+C`.

While the session is open, VNC into the home box, put the cursor in the window you
want to dictate into, and speak. Text shows up instantly.

### End a session

Press `Ctrl+C` in the laptop terminal running `remote-mic-client.sh`. The TCP module
is unloaded and the tunnel closes. On the home box, run:

```bash
./scripts/remote-mic-teardown.sh
```

...to kill the remote-mic voice_typer process and restart it against the local mic.
(You can also just re-launch from the tray.)

### Manual mode (if the client script can't reach the server for some reason)

On the **laptop**:

```bash
pactl load-module module-native-protocol-tcp port=4713 auth-anonymous=1 listen=127.0.0.1
ssh -R 127.0.0.1:4713:127.0.0.1:4713 ryan@home
```

On the **home box** (inside that SSH session):

```bash
/home/ryan/voice-to-text-system/scripts/remote-mic-server.sh 4713
```

## Gotchas

- **VNC locally, mic remotely.** Your laptop captures audio; the home box does
  transcription and typing. What you see via VNC is the home box's desktop,
  which receives the typed text.
- **Default source matters.** On your laptop, make sure the microphone you want
  to use is the default input. Check with `pactl get-default-source`; change
  with `pactl set-default-source <name>` or via your sound settings GUI.
- **Latency ~200–400ms** over a decent SSH link. For faster response, use a
  compressed SSH cipher (`-c aes128-gcm@openssh.com`) or run inside a LAN.
- **VAD sensitivity.** If your laptop mic is quieter than your home mic, the
  Silero VAD may miss soft speech. Lower `vad_threshold` in
  `~/.config/voice-to-text/config.ini` on the home box.
- **Mutual trust.** The `auth-anonymous=1` mode is only safe because the socket
  listens on `127.0.0.1` — the reverse SSH tunnel is the access path. Do NOT
  set `listen=0.0.0.0`.
