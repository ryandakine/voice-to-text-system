# Voice-to-Text System for Linux Mint

A system-wide voice-to-text application for Linux Mint that provides universal speech recognition with global hotkey support (F5). The system integrates with existing speech recognition components and provides seamless text insertion across all applications.

## Features

- **Global Hotkey**: Press F5 anywhere to start voice recording
- **Universal Text Insertion**: Works in browsers, text editors, terminals, and forms
- **Whisper Integration**: Uses OpenAI's Whisper for high-quality speech recognition
- **System Tray Integration**: Easy access to settings and status
- **Auto-start Support**: Configure to start automatically with your system
- **Privacy-Focused**: All processing happens locally on your machine
- **Health Integration** (NEW): Connect with Samsung Health and Whoop for health-aware responses
- **Real-time Monitoring**: Continuous health data sync and alert system
- **Emergency Protocols**: Automated emergency response with health monitoring

## System Requirements

- **OS**: Linux Mint 21.x or Ubuntu 22.04+
- **Python**: 3.8 or higher
- **Audio**: Working microphone input
- **Memory**: At least 2GB RAM (4GB+ recommended)
- **Storage**: 1GB free space for Whisper models

## Quick Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd voice-to-text-system
   ```

2. **Run the installation script**:
   ```bash
   chmod +x scripts/install.sh
   ./scripts/install.sh
   ```

3. **Start the system**:
   ```bash
   python3 src/main.py
   ```

## Manual Installation

If you prefer to install manually or the automated script doesn't work:

### 1. Install System Dependencies

```bash
sudo apt update
sudo apt install -y xbindkeys xdotool xclip python3-pip python3-pyaudio
sudo apt install -y libportaudio2 portaudio19-dev libasound2-dev
sudo apt install -y python3-gi python3-gi-cairo gir1.2-gtk-3.0
sudo apt install -y build-essential pkg-config pulseaudio-utils
```

### 2. Install Python Dependencies

```bash
python3 -m pip install --user SpeechRecognition pyaudio openai-whisper
python3 -m pip install --user PyGObject pynput keyboard psutil
python3 -m pip install --user numpy soundfile librosa
python3 -m pip install --user python-xlib pyautogui pyperclip
```

### 3. Create Configuration Directories

```bash
mkdir -p ~/.config/voice-to-text
mkdir -p ~/.local/share/voice-to-text/logs
mkdir -p ~/.cache/whisper
```

### 4. Configure xbindkeys

Create `~/.xbindkeysrc`:
```
# Voice-to-Text System Configuration
"/path/to/voice-to-text-system/scripts/hotkey_trigger.sh"
    F5
```

## Usage

### Basic Usage

1. **Start the system**:
   ```bash
   python3 src/main.py
   ```

2. **Press F5** anywhere to start voice recording
3. **Speak** your text clearly
4. **Press F5 again** to stop recording and insert text

### Advanced Usage

#### Enable Auto-start

```bash
# Enable the systemd service
systemctl --user enable voice-to-text.service

# Start the service
systemctl --user start voice-to-text.service
```

#### Customize Hotkey

Edit `~/.config/voice-to-text/config.ini`:
```ini
[General]
hotkey = F5
```

#### Change Whisper Model

Edit the configuration file:
```ini
[Whisper]
model = base  # Options: tiny, base, small, medium, large
```

## Configuration

The system configuration is stored in `~/.config/voice-to-text/config.ini`. Key settings:

### General Settings
- `hotkey`: Global hotkey (default: F5)
- `auto_start`: Enable auto-start (default: true)
- `show_system_tray`: Show system tray icon (default: true)

### Audio Settings
- `sample_rate`: Audio sample rate (default: 16000)
- `channels`: Number of audio channels (default: 1)
- `device_index`: Audio device index (-1 for default)

### Whisper Settings
- `model`: Whisper model size (tiny/base/small/medium/large)
- `language`: Language for transcription (auto for auto-detection)
- `task`: Task type (transcribe/translate)

### Text Insertion Settings
- `primary_method`: Primary insertion method (clipboard/keyboard/xdotool)
- `fallback_method`: Fallback insertion method
- `delay_before_insert`: Delay before text insertion (seconds)

## Troubleshooting

### Common Issues

#### 1. "No module named 'pyaudio'" Error

Install PortAudio development libraries:
```bash
sudo apt install -y portaudio19-dev python3-pyaudio
```

#### 2. Microphone Not Working

Check microphone permissions and settings:
```bash
# Check audio devices
python3 -c "import pyaudio; p = pyaudio.PyAudio(); print('Devices:', p.get_device_count())"

# Test microphone
python3 -c "import pyaudio; p = pyaudio.PyAudio(); print('Default input:', p.get_default_input_device_info())"
```

#### 3. Hotkey Not Working

Check xbindkeys configuration:
```bash
# Test xbindkeys
xbindkeys -n

# Check if xbindkeys is running
ps aux | grep xbindkeys
```

#### 4. Text Not Inserting

Test text insertion methods:
```bash
python3 -c "
from src.text_insertion import text_inserter
print('Testing insertion methods...')
results = text_inserter.test_insertion_methods()
print('Results:', results)
"
```

### Logs

Check application logs for detailed error information:
```bash
tail -f ~/.local/share/voice-to-text/logs/voice-to-text-$(date +%Y%m%d).log
```

### Performance Issues

1. **Use a smaller Whisper model** (tiny or base instead of large)
2. **Close other applications** to free up memory
3. **Check CPU usage** during processing
4. **Ensure adequate free disk space** for model caching

## Development

### Project Structure

```
voice-to-text-system/
├── src/                    # Source code
│   ├── main.py            # Main application
│   ├── voice_recorder.py  # Audio recording
│   ├── speech_processor.py # Whisper integration
│   ├── text_insertion.py  # Text insertion
│   ├── hotkey_handler.py  # Global hotkey
│   ├── gui/               # GUI components
│   └── utils/             # Utilities
├── scripts/               # Installation scripts
├── config/               # Configuration files
├── systemd/              # System service files
└── docs/                 # Documentation
```

### Running Tests

```bash
# Test audio system
python3 -c "from src.utils.audio_utils import audio_manager; print('Audio devices:', audio_manager.get_audio_devices())"

# Test Whisper
python3 -c "from src.speech_processor import speech_processor; print('Model info:', speech_processor.get_model_info())"

# Test text insertion
python3 -c "from src.text_insertion import text_inserter; print('Test results:', text_inserter.test_insertion_methods())"
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [OpenAI Whisper](https://github.com/openai/whisper) for speech recognition
- [PyAudio](https://people.csail.mit.edu/hubert/pyaudio/) for audio processing
- [xbindkeys](http://www.nongnu.org/xbindkeys/) for global hotkey support

## Support

For issues and questions:

1. Check the troubleshooting section above
2. Review the logs in `~/.local/share/voice-to-text/logs/`
3. Open an issue on the project repository
4. Check the documentation in the `docs/` directory

## Health Integration (NEW)

The voice-to-text system now includes comprehensive health monitoring capabilities:

### Setup Health Integration

1. **Install Health Dependencies**:
   ```bash
   pip install cryptography keyring requests
   cd src/health_integration
   npm install
   ```

2. **Configure Samsung Health** (Optional):
   ```python
   from src.health_integration import HealthMonitor

   monitor = HealthMonitor()
   monitor.configure_service("samsung_health", {
       "client_id": "your_client_id",
       "client_secret": "your_client_secret",
       "redirect_uri": "http://localhost:8080/callback/samsung"
   })
   ```

3. **Configure Whoop** (Optional):
   ```python
   monitor.configure_service("whoop", {
       "client_id": "your_client_id",
       "client_secret": "your_client_secret",
       "redirect_uri": "http://localhost:8080/callback/whoop"
   })
   ```

### Health-Aware Features

- **Smart Responses**: Voice responses adapt based on your health state
- **Real-time Alerts**: Automatic notifications for health concerns
- **Emergency Protocols**: Automated emergency response system
- **Personalized Tips**: Health recommendations based on your data
- **Voice Modifications**: Speech parameters adjust for health conditions

### Example Usage

```python
# Initialize health monitoring
monitor = HealthMonitor()
monitor.start_monitoring()

# Get health-aware response
user_input = "How am I feeling?"
response = monitor.get_health_aware_response(user_input)
print(response)  # Provides health status summary

# Get personalized health tips
tips = monitor.get_health_tips()
for tip in tips:
    print(f"💡 {tip}")
```

See `src/health_integration/README.md` for detailed documentation and `src/health_integration_example.py` for a complete integration example.

## Changelog

### Version 1.1.0 (Health Integration)
- Added comprehensive health monitoring system
- Samsung Health and Whoop API integrations
- Health-aware voice responses
- Real-time health data synchronization
- Emergency alert and response system
- Secure encrypted data storage
- Customizable health alerts and thresholds

### Version 1.0.0
- Initial release
- Global F5 hotkey support
- Whisper integration
- Universal text insertion
- System tray integration
- Auto-start capability

## AI Privacy Browser Fork

A Linux-native customization of the [browser-use](https://github.com/browser-use/browser-use) project is included under `browser_privacy_agent/`. It loads the uncensored `DavidAU/Qwen3-8B-64k-Context-2X-Josiefied-Uncensored` model locally (CUDA-only) with `<think>` templated prompts, Playwright stealth automations, optional Gradio UI, and cross-model validation for hallucination mitigation. Refer to [docs/AI_BROWSER_SETUP.md](docs/AI_BROWSER_SETUP.md) for fork instructions, installation steps (`install.sh`), systemd service usage (`ai-browser.service`), and privacy-oriented configuration (`.env.example`).
