"""Transcript history management for VoiceTyper.

Stores and retrieves past transcripts for review and export.

History writes are best-effort: I/O failures are logged and skipped,
never raised, so dictation cannot crash on disk-full / read-only / perm errors.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict


logger = logging.getLogger(__name__)


@dataclass
class TranscriptEntry:
    """A single transcript entry."""
    text: str
    timestamp: datetime
    duration_ms: Optional[int] = None
    confidence: Optional[float] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'text': self.text,
            'timestamp': self.timestamp.isoformat(),
            'duration_ms': self.duration_ms,
            'confidence': self.confidence,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'TranscriptEntry':
        """Create from dictionary."""
        return cls(
            text=data['text'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            duration_ms=data.get('duration_ms'),
            confidence=data.get('confidence'),
        )


class TranscriptHistory:
    """Manages transcript history storage and retrieval."""

    def __init__(self, history_dir: Optional[str] = None):
        if history_dir is None:
            history_dir = os.path.expanduser("~/.voice_typer/history")
        self.history_dir = Path(history_dir)
        self._history_dir_ok = False
        try:
            self.history_dir.mkdir(parents=True, exist_ok=True)
            self._history_dir_ok = True
        except OSError as e:
            logger.warning(
                "Could not create history dir %s: %s. History writes disabled.",
                self.history_dir, e,
            )

        self.current_session: List[TranscriptEntry] = []
        self.max_session_entries = 1000

    def add(self, text: str, duration_ms: Optional[int] = None,
            confidence: Optional[float] = None) -> None:
        """Add a transcript to history.

        Each utterance is appended immediately to today's JSONL file so a
        hard crash or OOM kill loses at most one utterance, never the
        accumulated session. The in-memory list is retained for fast
        get_recent / search / get_stats.
        """
        entry = TranscriptEntry(
            text=text,
            timestamp=datetime.now(),
            duration_ms=duration_ms,
            confidence=confidence,
        )
        self.current_session.append(entry)
        self._append_entry(entry)

        # Cap in-memory list. Disk already has the entry from _append_entry,
        # so trimming oldest is safe.
        if len(self.current_session) > self.max_session_entries:
            self.current_session = self.current_session[-self.max_session_entries:]

    def _daily_file(self, when: Optional[datetime] = None) -> Path:
        """Return today's history file path (history-YYYY-MM-DD.jsonl)."""
        if when is None:
            when = datetime.now()
        return self.history_dir / f"history-{when.strftime('%Y-%m-%d')}.jsonl"

    def _append_entry(self, entry: TranscriptEntry) -> None:
        """Append a single entry to today's JSONL file.

        Best-effort: one open/append/close per utterance. JSONL means a
        partial write only corrupts the last line — every prior utterance
        on disk is intact. I/O errors are logged and swallowed.
        """
        if not self._history_dir_ok:
            return

        path = self._daily_file()
        try:
            line = json.dumps(entry.to_dict())
        except (TypeError, ValueError) as e:
            logger.warning("Could not serialize history entry: %s", e)
            return

        try:
            with open(path, 'a', encoding='utf-8') as f:
                f.write(line + "\n")
        except OSError as e:
            logger.warning("Could not append to history file %s: %s", path, e)

    def _save_and_clear_session(self) -> None:
        """Flush in-memory session and clear.

        With per-utterance appends in add(), the daily file is already the
        source of truth on disk; this just clears the in-memory list. Kept
        for backwards compatibility with callers (e.g. save_session).
        """
        self.current_session.clear()

    def get_recent(self, n: int = 10) -> List[TranscriptEntry]:
        """Get recent transcripts."""
        return self.current_session[-n:]

    def search(self, query: str) -> List[TranscriptEntry]:
        """Search transcripts for query."""
        return [e for e in self.current_session if query.lower() in e.text.lower()]

    def save_session(self) -> None:
        """Manually save current session."""
        self._save_and_clear_session()

    def get_stats(self) -> Dict:
        """Get session statistics."""
        return {
            'session_entries': len(self.current_session),
            'total_chars': sum(len(e.text) for e in self.current_session),
            'avg_length': sum(len(e.text) for e in self.current_session) / len(self.current_session) if self.current_session else 0,
        }
