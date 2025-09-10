#!/usr/bin/env python3
"""
Test script for the voice-to-text system installation.
"""

import sys
import os
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_imports():
    """Test if all required modules can be imported."""
    print("Testing module imports...")
    
    try:
        import pyaudio
        print("✓ PyAudio imported successfully")
    except ImportError as e:
        print(f"✗ PyAudio import failed: {e}")
        return False
    
    try:
        import whisper
        print("✓ Whisper imported successfully")
    except ImportError as e:
        print(f"✗ Whisper import failed: {e}")
        return False
    
    try:
        import speech_recognition
        print("✓ SpeechRecognition imported successfully")
    except ImportError as e:
        print(f"✗ SpeechRecognition import failed: {e}")
        return False
    
    try:
        import numpy
        print("✓ NumPy imported successfully")
    except ImportError as e:
        print(f"✗ NumPy import failed: {e}")
        return False
    
    try:
        import pyautogui
        print("✓ PyAutoGUI imported successfully")
    except ImportError as e:
        print(f"✗ PyAutoGUI import failed: {e}")
        return False
    
    try:
        import pyperclip
        print("✓ PyPerclip imported successfully")
    except ImportError as e:
        print(f"✗ PyPerclip import failed: {e}")
        return False
    
    return True

def test_audio_system():
    """Test audio system functionality."""
    print("\nTesting audio system...")
    
    try:
        import pyaudio
        
        p = pyaudio.PyAudio()
        device_count = p.get_device_count()
        print(f"✓ Found {device_count} audio devices")
        
        # Get default input device
        try:
            default_device = p.get_default_input_device_info()
            print(f"✓ Default input device: {default_device['name']}")
        except Exception as e:
            print(f"✗ No default input device: {e}")
        
        # List input devices
        input_devices = []
        for i in range(device_count):
            try:
                device_info = p.get_device_info_by_index(i)
                if device_info['maxInputChannels'] > 0:
                    input_devices.append({
                        'index': i,
                        'name': device_info['name'],
                        'channels': device_info['maxInputChannels']
                    })
            except:
                pass
        
        print(f"✓ Found {len(input_devices)} input devices:")
        for device in input_devices:
            print(f"  - Device {device['index']}: {device['name']} ({device['channels']} channels)")
        
        p.terminate()
        return True
        
    except Exception as e:
        print(f"✗ Audio system test failed: {e}")
        return False

def test_whisper():
    """Test Whisper functionality."""
    print("\nTesting Whisper...")
    
    try:
        import whisper
        
        # Check available models
        models = ['tiny', 'base', 'small', 'medium', 'large']
        print(f"✓ Available Whisper models: {', '.join(models)}")
        
        # Try to load a small model
        print("Loading Whisper base model (this may take a moment)...")
        model = whisper.load_model("base")
        print("✓ Whisper model loaded successfully")
        
        return True
        
    except Exception as e:
        print(f"✗ Whisper test failed: {e}")
        return False

def test_system_components():
    """Test system components."""
    print("\nTesting system components...")
    
    try:
        # Test xbindkeys
        import subprocess
        result = subprocess.run(['which', 'xbindkeys'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ xbindkeys found")
        else:
            print("✗ xbindkeys not found")
            return False
        
        # Test xdotool
        result = subprocess.run(['which', 'xdotool'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ xdotool found")
        else:
            print("✗ xdotool not found")
            return False
        
        # Test xclip
        result = subprocess.run(['which', 'xclip'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ xclip found")
        else:
            print("✗ xclip not found")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ System components test failed: {e}")
        return False

def test_project_modules():
    """Test project-specific modules."""
    print("\nTesting project modules...")
    
    try:
        from src.utils.logger import logger
        print("✓ Logger module imported")
        
        from src.utils.config_manager import config
        print("✓ Config manager imported")
        
        from src.utils.audio_utils import audio_manager
        print("✓ Audio manager imported")
        
        from src.speech_processor import speech_processor
        print("✓ Speech processor imported")
        
        from src.text_insertion import text_inserter
        print("✓ Text inserter imported")
        
        from src.hotkey_handler import hotkey_handler
        print("✓ Hotkey handler imported")
        
        return True
        
    except Exception as e:
        print(f"✗ Project modules test failed: {e}")
        return False

def test_configuration():
    """Test configuration system."""
    print("\nTesting configuration...")
    
    try:
        from src.utils.config_manager import config
        
        # Test basic configuration
        hotkey = config.get('General', 'hotkey', 'F5')
        print(f"✓ Hotkey configured: {hotkey}")
        
        model = config.get('Whisper', 'model', 'base')
        print(f"✓ Whisper model configured: {model}")
        
        # Test audio configuration
        audio_config = config.get_audio_config()
        print(f"✓ Audio configuration: {audio_config}")
        
        return True
        
    except Exception as e:
        print(f"✗ Configuration test failed: {e}")
        return False

def test_directories():
    """Test required directories."""
    print("\nTesting directories...")
    
    directories = [
        Path.home() / ".config" / "voice-to-text",
        Path.home() / ".local" / "share" / "voice-to-text" / "logs",
        Path.home() / ".cache" / "whisper"
    ]
    
    for directory in directories:
        if directory.exists():
            print(f"✓ Directory exists: {directory}")
        else:
            print(f"✗ Directory missing: {directory}")
            try:
                directory.mkdir(parents=True, exist_ok=True)
                print(f"✓ Created directory: {directory}")
            except Exception as e:
                print(f"✗ Failed to create directory: {e}")
                return False
    
    return True

def main():
    """Run all tests."""
    print("Voice-to-Text System Installation Test")
    print("======================================")
    print()
    
    tests = [
        ("Module Imports", test_imports),
        ("Audio System", test_audio_system),
        ("Whisper", test_whisper),
        ("System Components", test_system_components),
        ("Project Modules", test_project_modules),
        ("Configuration", test_configuration),
        ("Directories", test_directories)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"Running: {test_name}")
        print('='*50)
        
        try:
            if test_func():
                passed += 1
                print(f"\n✓ {test_name} PASSED")
            else:
                print(f"\n✗ {test_name} FAILED")
        except Exception as e:
            print(f"\n✗ {test_name} FAILED with exception: {e}")
    
    print(f"\n{'='*50}")
    print("TEST SUMMARY")
    print('='*50)
    print(f"Passed: {passed}/{total}")
    print(f"Failed: {total - passed}/{total}")
    
    if passed == total:
        print("\n🎉 All tests passed! The voice-to-text system is ready to use.")
        print("\nTo start the system, run:")
        print("  python3 src/main.py")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please check the errors above.")
        print("\nCommon solutions:")
        print("1. Run the installation script: ./scripts/install.sh")
        print("2. Install missing dependencies manually")
        print("3. Check system requirements")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
