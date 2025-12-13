import pytest
from unittest.mock import patch
from pathlib import Path
import configparser

from src.utils.config_manager import ConfigManager

class TestConfigManager:
    def test_default_config_creation(self, mock_config_file):
        """Test that default configuration is created if file doesn't exist."""
        # Patch Path.home() to return the parent of our mock config dir
        # mock_config_file is tmp_path/.config/voice-to-text/config.ini
        # So home should be tmp_path
        
        fake_home = mock_config_file.parent.parent.parent
        
        with patch('pathlib.Path.home', return_value=fake_home):
            cm = ConfigManager()
            
            # Check if file was created
            assert cm.config_file.exists()
            assert cm.config_file == mock_config_file
            
            # Check default values
            assert cm.get('General', 'hotkey') == 'F5'
            assert cm.get('Whisper', 'model') == 'base'
            assert cm.getint('Audio', 'sample_rate') == 16000

    def test_load_existing_config(self, mock_config_file):
        """Test loading configuration from an existing file."""
        fake_home = mock_config_file.parent.parent.parent
        
        # Create existing config
        config = configparser.ConfigParser()
        config['General'] = {'hotkey': 'F10', 'auto_start': 'false'}
        config['Whisper'] = {'model': 'tiny'}
        
        with open(mock_config_file, 'w') as f:
            config.write(f)
            
        with patch('pathlib.Path.home', return_value=fake_home):
            cm = ConfigManager()
            
            assert cm.get('General', 'hotkey') == 'F10'
            assert cm.get('Whisper', 'model') == 'tiny'
            # Check default fallback works for missing keys if accessing directly
            # Note: ConfigManager currently doesn't merge defaults if section exists but key missing in all cases,
            # but get() has fallbacks
            assert cm.get('General', 'non_existent', 'default') == 'default'

    def test_update_config(self, mock_config_file):
        """Test updating configuration values."""
        fake_home = mock_config_file.parent.parent.parent
        
        with patch('pathlib.Path.home', return_value=fake_home):
            cm = ConfigManager()
            
            # Update value
            cm.update_hotkey('F12')
            
            # Check in memory
            assert cm.get('General', 'hotkey') == 'F12'
            
            # Check on disk
            new_conf = configparser.ConfigParser()
            new_conf.read(mock_config_file)
            assert new_conf['General']['hotkey'] == 'F12'

    def test_config_types(self, mock_config_file):
        """Test integer and boolean getters."""
        fake_home = mock_config_file.parent.parent.parent
        
        with patch('pathlib.Path.home', return_value=fake_home):
            cm = ConfigManager()
            
            # Test boolean
            cm.set('Test', 'is_true', 'true')
            cm.set('Test', 'is_false', 'false')
            
            assert cm.getboolean('Test', 'is_true') is True
            assert cm.getboolean('Test', 'is_false') is False
            
            # Test int
            cm.set('Test', 'number', '42')
            assert cm.getint('Test', 'number') == 42
