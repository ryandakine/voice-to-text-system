# VoiceTyper v2.0 Feature PRD

## Overview
Enhance VoiceTyper with 5 key features to improve usability, customization, and workflow integration.

## Features

### 1. Configurable Keyboard Shortcuts
**Goal:** Allow users to customize hotkeys without editing code.

**Requirements:**
- Config file (`~/.voice_typer/config.json`) for shortcut mapping
- Support customizing: toggle key, PTT keys, OpenClaw key, emergency stop
- Default to current keys (F8, Alt, F9, ESC)
- Runtime reload without restart

**Acceptance Criteria:**
- [ ] Config file created on first run if missing
- [ ] Invalid config falls back to defaults with warning
- [ ] Changes take effect immediately on save

---

### 2. Transcript History & Logging
**Goal:** Persistent storage and retrieval of all transcripts.

**Requirements:**
- SQLite database at `~/.voice_typer/history.db`
- Store: text, timestamp, duration, confidence
- Search by date range, text content
- Session statistics (word count, duration)
- Auto-cleanup old entries (>90 days)

**Acceptance Criteria:**
- [ ] Every transcript saved to database
- [ ] Query API for recent/search/filter
- [ ] Export session to file
- [ ] Configurable retention period

---

### 3. Voice Command Support
**Goal:** Control VoiceTyper hands-free with voice commands.

**Requirements:**
- Detect commands in speech before typing
- Commands: "stop listening", "start listening", "delete that", "computer help"
- Optional "computer" prefix for command mode
- Visual/audio feedback when command recognized
- Commands never typed to output

**Acceptance Criteria:**
- [ ] Commands intercepted and not typed
- [ ] "stop/start listening" toggles state
- [ ] "delete that" removes last typed text
- [ ] "computer help" shows available commands

---

### 4. Audio Device Selection
**Goal:** Choose specific microphone instead of system default.

**Requirements:**
- List all input devices with index, name, sample rate
- Select by index or name pattern
- Save preference to config
- Auto-select USB mic if available
- Handle device disconnect/reconnect

**Acceptance Criteria:**
- [ ] Device list displayed on startup
- [ ] Configurable default device
- [ ] Graceful fallback if selected device unavailable
- [ ] CLI flag to list devices without running

---

### 5. Transcript Export
**Goal:** Export transcripts to multiple formats for sharing/archiving.

**Requirements:**
- Formats: TXT, JSON, CSV, SRT (subtitles), Markdown
- Export current session or date range
- Include/exclude timestamps
- Hotkey to quick-export (F10)
- Default export directory: `~/Documents/VoiceTyper/`

**Acceptance Criteria:**
- [ ] All 5 formats export correctly
- [ ] F10 triggers quick export
- [ ] Filenames include timestamp
- [ ] Export notification shown

---

## Implementation Plan

### Phase 1: Core Infrastructure
1. Create config module with JSON persistence
2. Create database module with SQLite
3. Refactor main class to use new modules

### Phase 2: Features 1, 2, 4
1. Keyboard shortcuts with config
2. Audio device selection
3. History logging to database

### Phase 3: Features 3, 5
1. Voice command detection
2. Export functionality
3. Integration testing

### Phase 4: Polish
1. Error handling
2. Documentation updates
3. System tray integration

---

## Technical Notes

### Dependencies to Add
```
pysqlite3 (usually built-in)
```

### Config Schema
```json
{
  "shortcuts": {
    "toggle": "f8",
    "ptt": ["alt_l", "alt_r"],
    "openclaw": "f9",
    "emergency_stop": "esc",
    "export": "f10"
  },
  "audio": {
    "device_index": null,
    "sample_rate": 16000,
    "channels": 1
  },
  "history": {
    "enabled": true,
    "retention_days": 90,
    "db_path": "~/.voice_typer/history.db"
  },
  "export": {
    "default_format": "txt",
    "output_dir": "~/Documents/VoiceTyper",
    "include_timestamps": true
  },
  "voice_commands": {
    "enabled": true,
    "prefix": "computer"
  }
}
```

### Database Schema
```sql
CREATE TABLE transcripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    duration_ms INTEGER,
    confidence REAL,
    session_id TEXT
);

CREATE INDEX idx_timestamp ON transcripts(timestamp);
CREATE INDEX idx_session ON transcripts(session_id);
```

---

## Success Metrics
- All 5 features functional and tested
- No regression in core voice typing
- Startup time < 3 seconds
- Memory usage < 200MB
