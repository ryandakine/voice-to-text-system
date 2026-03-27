"""Transcript history management for VoiceTyper.

Stores and retrieves past transcripts for review and export.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict


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
        self.history_dir.mkdir(parents=True, exist_ok=True)
        
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
        """Save current session to disk and clear."""
        if not self.current_session:
            return
            
        filename = self.history_dir / f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        data = [entry.to_dict() for entry in self.current_session]
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
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
