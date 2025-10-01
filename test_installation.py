#!/usr/bin/env python3
"""Test script for the voice-to-text system installation.

The script validates that required runtime dependencies and system
components are available. Set the ``ALLOW_PARTIAL_INSTALL_TESTS``
environment variable to ``1`` to downgrade missing optional dependencies
to skips instead of hard failures, which is useful in constrained test
environments where native packages cannot be installed.
"""

import sys
import os
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional
from pathlib import Path


class TestStatus(Enum):
    """Enumeration of supported test outcomes."""

    PASSED = auto()
    FAILED = auto()
    SKIPPED = auto()


@dataclass
class TestResult:
    """Container describing the result of a single test."""

    name: str
    status: TestStatus
    message: str = ""


class MissingDependencyError(RuntimeError):
    """Raised when a dependency is not available for a test."""

    def __init__(self, dependency: str, message: Optional[str] = None):
        detail = message or f"Missing dependency: {dependency}"
        super().__init__(detail)
        self.dependency = dependency


ALLOW_PARTIAL = os.getenv("ALLOW_PARTIAL_INSTALL_TESTS", "0") == "1"

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
        raise MissingDependencyError("pyaudio", str(e)) from e

    try:
        import whisper
        print("✓ Whisper imported successfully")
    except ImportError as e:
        print(f"✗ Whisper import failed: {e}")
        raise MissingDependencyError("whisper", str(e)) from e

    try:
        import speech_recognition
        print("✓ SpeechRecognition imported successfully")
    except ImportError as e:
        print(f"✗ SpeechRecognition import failed: {e}")
        raise MissingDependencyError("speech_recognition", str(e)) from e

    try:
        import numpy
        print("✓ NumPy imported successfully")
    except ImportError as e:
        print(f"✗ NumPy import failed: {e}")
        raise MissingDependencyError("numpy", str(e)) from e

    try:
        import pyautogui
        print("✓ PyAutoGUI imported successfully")
    except ImportError as e:
        print(f"✗ PyAutoGUI import failed: {e}")
        raise MissingDependencyError("pyautogui", str(e)) from e

    try:
        import pyperclip
        print("✓ PyPerclip imported successfully")
    except ImportError as e:
        print(f"✗ PyPerclip import failed: {e}")
        raise MissingDependencyError("pyperclip", str(e)) from e

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

    except ImportError as e:
        print(f"✗ Audio system test failed: {e}")
        raise MissingDependencyError("pyaudio", str(e)) from e
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

    except ImportError as e:
        print(f"✗ Whisper test failed: {e}")
        raise MissingDependencyError("whisper", str(e)) from e
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
            message = "xbindkeys not found"
            print(f"✗ {message}")
            raise MissingDependencyError("xbindkeys", message)

        # Test xdotool
        result = subprocess.run(['which', 'xdotool'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ xdotool found")
        else:
            message = "xdotool not found"
            print(f"✗ {message}")
            raise MissingDependencyError("xdotool", message)

        # Test xclip
        result = subprocess.run(['which', 'xclip'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ xclip found")
        else:
            message = "xclip not found"
            print(f"✗ {message}")
            raise MissingDependencyError("xclip", message)

        return True

    except MissingDependencyError:
        raise
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

    except ImportError as e:
        print(f"✗ Project modules test failed: {e}")
        raise MissingDependencyError(e.name or "unknown", str(e)) from e
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

    except ImportError as e:
        print(f"✗ Configuration test failed: {e}")
        raise MissingDependencyError(e.name or "unknown", str(e)) from e
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


def run_test(test_name, test_func):
    """Run a single test function and normalize the result."""

    print(f"\n{'='*50}")
    print(f"Running: {test_name}")
    print('='*50)

    try:
        if test_func():
            print(f"\n✓ {test_name} PASSED")
            return TestResult(test_name, TestStatus.PASSED)
        print(f"\n✗ {test_name} FAILED")
        return TestResult(test_name, TestStatus.FAILED)
    except MissingDependencyError as error:
        if ALLOW_PARTIAL:
            print(f"\n⚠️  {test_name} SKIPPED due to missing dependency: {error.dependency}")
            print(f"   Details: {error}")
            return TestResult(test_name, TestStatus.SKIPPED, str(error))
        print(f"\n✗ {test_name} FAILED due to missing dependency: {error.dependency}")
        print(f"   Details: {error}")
        return TestResult(test_name, TestStatus.FAILED, str(error))
    except Exception as error:  # pragma: no cover - diagnostic output only
        print(f"\n✗ {test_name} FAILED with exception: {error}")
        return TestResult(test_name, TestStatus.FAILED, str(error))

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

    results = [run_test(name, func) for name, func in tests]

    passed = sum(1 for result in results if result.status == TestStatus.PASSED)
    skipped = sum(1 for result in results if result.status == TestStatus.SKIPPED)
    total = len(results)

    print(f"\n{'='*50}")
    print("TEST SUMMARY")
    print('='*50)
    print(f"Passed: {passed}/{total}")
    print(f"Skipped: {skipped}/{total}")
    failed = total - passed - skipped
    print(f"Failed: {failed}/{total}")

    if failed == 0:
        print("\n🎉 All tests passed! The voice-to-text system is ready to use.")
        print("\nTo start the system, run:")
        print("  python3 src/main.py")
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please check the errors above.")
        print("\nCommon solutions:")
        print("1. Run the installation script: ./scripts/install.sh")
        print("2. Install missing dependencies manually")
        print("3. Check system requirements")

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
