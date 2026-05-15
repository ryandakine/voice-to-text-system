# Push-to-Talk Voice-to-Text System

## 🎤 How to Use

Your voice-to-text system is now running with **push-to-talk** functionality!

### Basic Usage:
1. **Hold down the Alt key** (either left or right Alt)
2. **Speak clearly** while holding Alt
3. **Release the Alt key** to stop recording and transcribe
4. The text will be automatically inserted where your cursor is

### Quick Commands:
- **Alt (hold)**: Start recording
- **Alt (release)**: Stop recording & transcribe
- **ESC**: Emergency stop (if recording gets stuck)
- **Ctrl+C**: Exit the application

## 🚀 Starting the System

### Method 1: Command Line
```bash
cd $REPO_DIR
.venv/bin/python start_push_to_talk.py
```

### Method 2: Background Process
```bash
cd $REPO_DIR
nohup .venv/bin/python start_push_to_talk.py > push_to_talk.log 2>&1 &
```

## 📊 Check Status

### See if it's running:
```bash
ps aux | grep push_to_talk
```

### View logs:
```bash
tail -f $REPO_DIR/push_to_talk.log
```

### Stop the system:
```bash
pkill -f push_to_talk
```

## 🔧 Troubleshooting

### If Alt key conflicts with other applications:
- The system monitors both left and right Alt keys
- It won't interfere with Alt+Tab or other Alt combinations
- Just release Alt quickly when using shortcuts

### If recording doesn't start:
1. Check if the process is running
2. Make sure your microphone is working
3. Check the log file for errors

### If text doesn't insert:
- Make sure your cursor is in a text field
- The system uses clipboard insertion by default
- Some applications may require different insertion methods

## 📝 Console Indicators

When running, you'll see these indicators in the console:
- 🔴 **RECORDING...** - Alt key is held, recording audio
- ⭕ **Recording stopped** - Alt released, recording complete
- 🔄 **Processing audio...** - Transcribing speech
- ✅ **Processing complete** - Text has been inserted

## ⚙️ Configuration

The system is configured to:
- Use the **base** Whisper model (good balance of speed/accuracy)
- Record at 16kHz sample rate
- Maximum recording duration: 30 seconds
- Auto-insert text after transcription

## 🎯 Tips for Best Results

1. **Speak clearly** and at a normal pace
2. **Hold Alt before speaking** to capture the beginning
3. **Release Alt after finishing** your sentence
4. **Use in quiet environments** for better accuracy
5. **Short phrases work best** (under 30 seconds)

## 🔄 Switch Back to F5 Toggle Mode

If you prefer the old F5 toggle mode:
```bash
cd $REPO_DIR
.venv/bin/python src/main.py
```

## 📚 File Locations

- Main script: `$REPO_DIR/start_push_to_talk.py`
- Push-to-talk handler: `$REPO_DIR/src/push_to_talk_handler.py`
- Main application: `$REPO_DIR/src/main_push_to_talk.py`
- Logs: `$REPO_DIR/push_to_talk.log`
- Whisper models: `~/.cache/whisper/`

---

**Note**: The first time you run the system, it will download the Whisper model (about 140MB). This only happens once.
