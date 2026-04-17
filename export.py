"""Export functionality for VoiceTyper transcripts."""
import json
import csv
from datetime import datetime
from pathlib import Path
from typing import List, Optional

class TranscriptExporter:
    """Exports transcripts to various formats."""
    
    SUPPORTED_FORMATS = ['txt', 'json', 'csv', 'srt', 'md']
    
    def export(self, transcripts: List[dict], output_path: str) -> bool:
        fmt = Path(output_path).suffix.lstrip('.').lower()
        try:
            if fmt == 'txt':
                self._export_txt(transcripts, output_path)
            elif fmt == 'json':
                self._export_json(transcripts, output_path)
            elif fmt == 'csv':
                self._export_csv(transcripts, output_path)
            elif fmt == 'srt':
                self._export_srt(transcripts, output_path)
            elif fmt == 'md':
                self._export_md(transcripts, output_path)
            return True
        except Exception as e:
            print(f"Export error: {e}")
            return False
    
    def _export_txt(self, transcripts, path):
        with open(path, 'w', encoding='utf-8') as f:
            for t in transcripts:
                f.write(f"{t['text']}\n")
    
    def _export_json(self, transcripts, path):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(transcripts, f, indent=2, ensure_ascii=False)
    
    def _export_csv(self, transcripts, path):
        with open(path, 'w', newline='', encoding='utf-8') as f:
            if transcripts:
                writer = csv.DictWriter(f, fieldnames=transcripts[0].keys())
                writer.writeheader()
                writer.writerows(transcripts)
    
    def _export_srt(self, transcripts, path):
        with open(path, 'w', encoding='utf-8') as f:
            for i, t in enumerate(transcripts, 1):
                start = f"{(i-1)//3600:02d}:{((i-1)%3600)//60:02d}:{(i-1)%60:02d},000"
                end = f"{i//3600:02d}:{(i%3600)//60:02d}:{i%60:02d},000"
                f.write(f"{i}\n{start} --> {end}\n{t['text']}\n\n")
    
    def _export_md(self, transcripts, path):
        with open(path, 'w', encoding='utf-8') as f:
            f.write("# VoiceTyper Transcript\n\n")
            for t in transcripts:
                f.write(f"{t['text']}\n\n")
