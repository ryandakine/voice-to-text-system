#!/usr/bin/env python3
"""
Launcher for the Voice-to-Text System
"""

import sys
import argparse
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def main():
    """Main launcher function."""
    parser = argparse.ArgumentParser(description="Voice-to-Text System Launcher")
    parser.add_argument(
        "--gui", "-g",
        action="store_true",
        help="Launch the GUI manager instead of the main system"
    )
    parser.add_argument(
        "--test", "-t",
        action="store_true",
        help="Run installation tests"
    )
    parser.add_argument(
        "--install", "-i",
        action="store_true",
        help="Run the installation script"
    )
    
    args = parser.parse_args()
    
    if args.test:
        # Run installation tests
        print("Running installation tests...")
        try:
            from test_installation import main as test_main
            success = test_main()
            sys.exit(0 if success else 1)
        except ImportError as e:
            print(f"Error: Could not import test module: {e}")
            sys.exit(1)
    
    elif args.install:
        # Run installation
        print("Running installation...")
        import subprocess
        try:
            subprocess.run(["./scripts/install.sh"], check=True)
            print("Installation completed successfully!")
        except subprocess.CalledProcessError as e:
            print(f"Installation failed: {e}")
            sys.exit(1)
        except FileNotFoundError:
            print("Error: install.sh not found")
            sys.exit(1)
    
    elif args.gui:
        # Launch GUI manager
        print("Launching Voice-to-Text System Manager...")
        try:
            from src.gui.manager import main as gui_main
            gui_main()
        except ImportError as e:
            print(f"Error: Could not import GUI manager: {e}")
            print("Make sure GTK3 Python bindings are installed:")
            print("  sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0")
            sys.exit(1)
        except Exception as e:
            print(f"Error launching GUI manager: {e}")
            sys.exit(1)
    
    else:
        # Launch main system
        print("Launching Voice-to-Text System...")
        try:
            from src.main import main as system_main
            success = system_main()
            sys.exit(0 if success else 1)
        except ImportError as e:
            print(f"Error: Could not import main system: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Error launching main system: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
