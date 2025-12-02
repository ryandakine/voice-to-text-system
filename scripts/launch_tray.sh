#!/bin/bash
cd "$(dirname "$0")/.."
source venv/bin/activate
python src/tray_icon.py
