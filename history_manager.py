"""Transcript history management with SQLite."""
import sqlite3
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import logging


class HistoryManager:
    """Manages transcript history with SQLite backend."""
    
    def __init__(self, db_path: Optional[str] = None, retention_days: int = 90):
        if db_path is None:
            db_path = os.path.expanduser("~/.voice_typer/history.db")
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.retention_days = retention_days
        self.session_id = str(uuid.uuid4())[:8]
        
        self._init_db()
        self._cleanup_old()
    
    def _init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS transcripts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    duration_ms INTEGER,
                    confidence REAL,
                    session_id TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON transcripts(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_session ON transcripts(session_id)")
            conn.commit()
    
    def add(self, text: str, duration_ms: Optional[int] = None,
            confidence: Optional[float] = None) -> None:
        """Add a transcript to history."""
        if not text or not text.strip():
            return
            
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO transcripts (text, duration_ms, confidence, session_id) VALUES (?, ?, ?, ?)",
                    (text.strip(), duration_ms, confidence, self.session_id)
                )
                conn.commit()
        except Exception as e:
            logging.error(f"Error saving to history: {e}")
    
    def get_recent(self, n: int = 10) -> List[Dict]:
        """Get recent transcripts."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT * FROM transcripts ORDER BY timestamp DESC LIMIT ?",
                    (n,)
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logging.error(f"Error reading history: {e}")
            return []
    
    def search(self, query: str, limit: int = 50) -> List[Dict]:
        """Search transcripts by text content."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT * FROM transcripts WHERE text LIKE ? ORDER BY timestamp DESC LIMIT ?",
                    (f"%{query}%", limit)
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logging.error(f"Error searching history: {e}")
            return []
    
    def get_session_transcripts(self, session_id: Optional[str] = None) -> List[Dict]:
        """Get all transcripts for a session."""
        if session_id is None:
            session_id = self.session_id
            
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT * FROM transcripts WHERE session_id = ? ORDER BY timestamp",
                    (session_id,)
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logging.error(f"Error reading session: {e}")
            return []
    
    def get_stats(self) -> Dict:
        """Get history statistics."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT COUNT(*), SUM(LENGTH(text)) FROM transcripts")
                count, total_chars = cursor.fetchone()
                
                cursor = conn.execute("SELECT COUNT(DISTINCT session_id) FROM transcripts")
                sessions = cursor.fetchone()[0]
                
                return {
                    "total_entries": count or 0,
                    "total_chars": total_chars or 0,
                    "sessions": sessions or 0,
                    "avg_length": (total_chars / count) if count else 0
                }
        except Exception as e:
            logging.error(f"Error getting stats: {e}")
            return {"total_entries": 0, "total_chars": 0, "sessions": 0, "avg_length": 0}
    
    def _cleanup_old(self) -> None:
        """Remove entries older than retention period."""
        if self.retention_days <= 0:
            return
            
        cutoff = datetime.now() - timedelta(days=self.retention_days)
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM transcripts WHERE timestamp < ?",
                    (cutoff.isoformat(),)
                )
                if cursor.rowcount > 0:
                    logging.info(f"Cleaned up {cursor.rowcount} old history entries")
                conn.commit()
        except Exception as e:
            logging.error(f"Error cleaning up history: {e}")
    
    def export_to_list(self, start_date: Optional[datetime] = None,
                       end_date: Optional[datetime] = None) -> List[Dict]:
        """Export transcripts to list for other formats."""
        query = "SELECT * FROM transcripts WHERE 1=1"
        params = []
        
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date.isoformat())
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date.isoformat())
        
        query += " ORDER BY timestamp"
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logging.error(f"Error exporting: {e}")
            return []
