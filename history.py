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
        """Add a transcript to history."""
        entry = TranscriptEntry(
            text=text,
            timestamp=datetime.now(),
            duration_ms=duration_ms,
            confidence=confidence,
        )
        self.current_session.append(entry)

        # Keep only last N entries in memory
        if len(self.current_session) > self.max_session_entries:
            self._save_and_clear_session()

    def _save_and_clear_session(self) -> None:
        """Save current session to disk and clear.

        File I/O errors (disk full, read-only mount, permission denied) are
        logged and swallowed so the dictation flow never crashes. On failure
        the in-memory session is preserved for the next attempt.
        """
        if not self.current_session:
            return

        if not self._history_dir_ok:
            # History dir unwritable; drop to avoid unbounded memory growth.
            self.current_session.clear()
            return

        filename = self.history_dir / f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        data = [entry.to_dict() for entry in self.current_session]

        try:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
        except (OSError, TypeError, ValueError) as e:
            logger.warning("Could not write history file %s: %s", filename, e)
            return

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
