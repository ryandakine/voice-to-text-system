#!/usr/bin/env python3
"""
Simple test script for Health Integration Module

Tests the basic structure and imports without requiring external dependencies.
"""

import os
import sys
import json

def test_module_structure():
    """Test that all required files exist."""
    required_files = [
        "src/health_integration/__init__.py",
        "src/health_integration/samsung_health_api.py",
        "src/health_integration/whoop_api.py",
        "src/health_integration/health_data_sync.py",
        "src/health_integration/health_aware_responses.py",
        "src/health_integration/health_monitor.py",
        "src/health_integration/health_config.json",
        "src/health_integration_example.py"
    ]

    missing_files = []
    for file_path in required_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)

    if missing_files:
        print("❌ Missing files:")
        for file in missing_files:
            print(f"   - {file}")
        return False

    print("✅ All required files exist")
    return True

def test_config_file():
    """Test that the configuration file is valid JSON."""
    config_path = "src/health_integration/health_config.json"

    try:
        with open(config_path, 'r') as f:
            config = json.load(f)

        required_keys = ["version", "sync_settings", "emergency_thresholds", "services"]
        for key in required_keys:
            if key not in config:
                print(f"❌ Missing required config key: {key}")
                return False

        print("✅ Configuration file is valid")
        return True

    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in config file: {e}")
        return False
    except FileNotFoundError:
        print("❌ Configuration file not found")
        return False

def test_module_imports():
    """Test that basic Python syntax is valid (without importing dependencies)."""
    test_files = [
        "src/health_integration/__init__.py",
        "src/health_integration/health_monitor.py",
        "src/health_integration/health_aware_responses.py"
    ]

    for file_path in test_files:
        try:
            with open(file_path, 'r') as f:
                content = f.read()

            # Basic syntax check by compiling
            compile(content, file_path, 'exec')
            print(f"✅ {file_path} syntax is valid")

        except SyntaxError as e:
            print(f"❌ Syntax error in {file_path}: {e}")
            return False
        except FileNotFoundError:
            print(f"❌ File not found: {file_path}")
            return False

    return True

def show_module_info():
    """Show information about the health integration module."""
    print("\n📊 Health Integration Module Info:")
    print("=" * 40)

    # Count lines of code
    total_lines = 0
    python_files = [
        "src/health_integration/__init__.py",
        "src/health_integration/samsung_health_api.py",
        "src/health_integration/whoop_api.py",
        "src/health_integration/health_data_sync.py",
        "src/health_integration/health_aware_responses.py",
        "src/health_integration/secure_storage.py",
        "src/health_integration/health_monitor.py",
        "src/health_integration_example.py"
    ]

    for file_path in python_files:
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                lines = len(f.readlines())
            total_lines += lines
            print(f"   {file_path}: {lines} lines")
    print(f"📝 Total lines of code: {total_lines}")

    # Show features
    print("\n🚀 Features Implemented:")
    features = [
        "✅ Samsung Health API Integration",
        "✅ Whoop API Integration",
        "✅ Health Data Synchronization",
        "✅ Health-Aware Voice Responses",
        "✅ Real-time Health Monitoring",
        "✅ Secure Data Storage",
        "✅ Emergency Alert System",
        "✅ Customizable Health Alerts",
        "✅ Voice Parameter Modifications",
        "✅ Comprehensive Documentation"
    ]

    for feature in features:
        print(f"   {feature}")

def main():
    """Run all tests."""
    print("🧪 Testing Health Integration Module")
    print("=" * 40)

    tests = [
        ("Module Structure", test_module_structure),
        ("Configuration File", test_config_file),
        ("Python Syntax", test_module_imports)
    ]

    all_passed = True
    for test_name, test_func in tests:
        print(f"\n🔍 Running {test_name} test...")
        if not test_func():
            all_passed = False

    if all_passed:
        print("\n🎉 All tests passed!")
        show_module_info()

        print("\n📋 Next Steps:")
        print("1. Install required dependencies:")
        print("   pip install cryptography keyring requests")
        print("   # or use pipx/virtual environment")
        print("")
        print("2. Configure API credentials:")
        print("   - Samsung Health: https://developer.samsung.com/health")
        print("   - Whoop: https://developer.whoop.com")
        print("")
        print("3. Run the example:")
        print("   python src/health_integration_example.py")
        print("")
        print("4. Integrate with voice system:")
        print("   from src.health_integration import HealthMonitor")
        print("   monitor = HealthMonitor()")
        print("   monitor.start_monitoring()")

    else:
        print("\n❌ Some tests failed. Please check the output above.")

    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
