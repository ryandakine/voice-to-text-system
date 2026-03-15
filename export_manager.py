"""Export functionality for VoiceTyper transcripts."""
import json
import csv
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import os


class ExportManager:
    """Exports transcripts to various formats."""
    
    SUPPORTED_FORMATS = ['txt', 'json', 'csv', 'srt', 'md']
    
    def __init__(self, output_dir: Optional[str] = None):
        if output_dir is None:
            output_dir = os.path.expanduser("~/Documents/VoiceTyper")
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def export(self, transcripts: List[Dict], filename: Optional[str] = None,
               fmt: Optional[str] = None, include_timestamps: bool = True) -> Optional[Path]:
        """Export transcripts to file.
        
        Args:
            transcripts: List of transcript dicts
            filename: Output filename (auto-generated if None)
            fmt: Format override (detected from filename if None)
            include_timestamps: Whether to include timestamps
            
        Returns:
            Path to exported file or None on error
        """
        if not transcripts:
            return None
        
        # Generate filename if not provided
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"transcript_{timestamp}.txt"
        
        output_path = self.output_dir / filename
        
        # Detect format from extension
        if fmt is None:
            fmt = output_path.suffix.lstrip('.').lower()
        if fmt not in self.SUPPORTED_FORMATS:
            fmt = 'txt'
        
        try:
            if fmt == 'txt':
                self._export_txt(transcripts, output_path, include_timestamps)
            elif fmt == 'json':
                self._export_json(transcripts, output_path)
            elif fmt == 'csv':
                self._export_csv(transcripts, output_path)
            elif fmt == 'srt':
                self._export_srt(transcripts, output_path)
            elif fmt == 'md':
                self._export_md(transcripts, output_path, include_timestamps)
            
            return output_path
        except Exception as e:
            print(f"Export error: {e}")
            return None
    
    def _export_txt(self, transcripts: List[Dict], path: Path, include_timestamps: bool) -> None:
        """Export as plain text."""
        with open(path, 'w', encoding='utf-8') as f:
            for t in transcripts:
                if include_timestamps and 'timestamp' in t:
                    ts = t['timestamp']
                    if isinstance(ts, datetime):
                        ts = ts.strftime("%Y-%m-%d %H:%M:%S")
                    f.write(f"[{ts}] ")
                f.write(f"{t.get('text', '')}\n")
    
    def _export_json(self, transcripts: List[Dict], path: Path) -> None:
        """Export as JSON."""
        # Convert datetime to string
        data = []
        for t in transcripts:
            item = dict(t)
            if 'timestamp' in item and isinstance(item['timestamp'], datetime):
                item['timestamp'] = item['timestamp'].isoformat()
            data.append(item)
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _export_csv(self, transcripts: List[Dict], path: Path) -> None:
        """Export as CSV."""
        with open(path, 'w', newline='', encoding='utf-8') as f:
            if transcripts:
                fieldnames = list(transcripts[0].keys())
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for t in transcripts:
                    row = dict(t)
                    if 'timestamp' in row and isinstance(row['timestamp'], datetime):
                        row['timestamp'] = row['timestamp'].strftime("%Y-%m-%d %H:%M:%S")
                    writer.writerow(row)
    
    def _export_srt(self, transcripts: List[Dict], path: Path) -> None:
        """Export as SRT subtitles."""
        with open(path, 'w', encoding='utf-8') as f:
            for i, t in enumerate(transcripts, 1):
                # Estimate timing (5 seconds per entry)
                start_sec = (i - 1) * 5
                end_sec = i * 5
                
                start_time = f"{start_sec // 3600:02d}:{(start_sec % 3600) // 60:02d}:{start_sec % 60:02d},000"
                end_time = f"{end_sec // 3600:02d}:{(end_sec % 3600) // 60:02d}:{end_sec % 60:02d},000"
                
                f.write(f"{i}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{t.get('text', '')}\n\n")
    
    def _export_md(self, transcripts: List[Dict], path: Path, include_timestamps: bool) -> None:
        """Export as Markdown."""
        with open(path, 'w', encoding='utf-8') as f:
            f.write("# VoiceTyper Transcript\n\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("---\n\n")
            
            for t in transcripts:
                if include_timestamps and 'timestamp' in t:
                    ts = t['timestamp']
                    if isinstance(ts, datetime):
                        ts = ts.strftime("%Y-%m-%d %H:%M:%S")
                    f.write(f"**[{ts}]** ")
                f.write(f"{t.get('text', '')}\n\n")
    
    def quick_export(self, transcripts: List[Dict], fmt: str = 'txt') -> Optional[Path]:
        """Quick export with auto-filename."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"transcript_{timestamp}.{fmt}"
        return self.export(transcripts, filename, fmt)
