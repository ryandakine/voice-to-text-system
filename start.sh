#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

"$PROJECT_DIR/.venv/bin/python" "$PROJECT_DIR/src/main.py"
