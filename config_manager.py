"""Configuration management for VoiceTyper."""
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

DEFAULT_CONFIG = {
    "shortcuts": {
        "toggle": "f8",
        "ptt": ["alt_l", "alt_r", "alt"],
        "openclaw": "f9",
        "emergency_stop": "esc",
        "export": "f10"
    },
    "audio": {
        "device_index": None,
        "sample_rate": 16000,
        "channels": 1
    },
    "history": {
        "enabled": True,
        "retention_days": 90,
        "db_path": "~/.voice_typer/history.db"
    },
    "export": {
        "default_format": "txt",
        "output_dir": "~/Documents/VoiceTyper",
        "include_timestamps": True
    },
    "voice_commands": {
        "enabled": True,
        "prefix": "computer"
    }
}

class ConfigManager:
    """Manages VoiceTyper configuration."""
    
    def __init__(self, config_dir: Optional[str] = None):
        if config_dir is None:
            config_dir = os.path.expanduser("~/.voice_typer")
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self.config_file = self.config_dir / "config.json"
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load config from file or create default."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    user_config = json.load(f)
                # Merge with defaults
                config = DEFAULT_CONFIG.copy()
                self._deep_update(config, user_config)
                return config
            except Exception as e:
                logging.warning(f"Error loading config: {e}, using defaults")
                return DEFAULT_CONFIG.copy()
        else:
            # Create default config
            self._save_config(DEFAULT_CONFIG)
            return DEFAULT_CONFIG.copy()
    
    def _deep_update(self, base: Dict, update: Dict) -> None:
        """Deep merge update into base."""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_update(base[key], value)
            else:
                base[key] = value
    
    def _save_config(self, config: Dict) -> None:
        """Save config to file."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            logging.error(f"Error saving config: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get config value by dot notation (e.g., 'shortcuts.toggle')."""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def set(self, key: str, value: Any) -> None:
        """Set config value by dot notation."""
        keys = key.split('.')
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        self._save_config(self.config)
    
    def get_shortcut(self, action: str) -> str or List[str]:
        """Get shortcut for an action."""
        return self.config["shortcuts"].get(action, DEFAULT_CONFIG["shortcuts"][action])
    
    def get_toggle_key(self) -> str:
        """Get toggle key (e.g., 'f8')."""
        return self.get_shortcut("toggle")
    
    def get_ptt_keys(self) -> List[str]:
        """Get PTT keys."""
        return self.get_shortcut("ptt")
    
    def reload(self) -> None:
        """Reload config from disk."""
        self.config = self._load_config()
        logging.info("Config reloaded")
