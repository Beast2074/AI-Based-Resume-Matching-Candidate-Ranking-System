#!/usr/bin/env bash
set -e

# Run the bundle size checker script with python
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_EXEC="python"

if [ -f "$SCRIPT_DIR/../.venv/bin/python" ]; then
    PYTHON_EXEC="$SCRIPT_DIR/../.venv/bin/python"
elif [ -f "$SCRIPT_DIR/../.venv/Scripts/python.exe" ]; then
    PYTHON_EXEC="$SCRIPT_DIR/../.venv/Scripts/python.exe"
fi

"$PYTHON_EXEC" "$SCRIPT_DIR/check_bundle_size.py"
