#!/bin/bash
cd "$(dirname "$0")/.."
source venv/bin/activate
python src/status_gui.py
