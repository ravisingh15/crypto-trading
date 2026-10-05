#!/usr/bin/env bash
set -e

# Change to the project directory
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "======================================================================"
echo "   CYPHERSCREEN : Live Binance Market Screener & Trading Engine"
echo "======================================================================"
echo ""

# 1. Detect Python environment (.venv, venv, conda, or system python3)
PY_CMD=""
if [ -f ".venv/bin/python" ]; then
    PY_CMD=".venv/bin/python"
    echo "[*] Using local virtual environment: .venv"
elif [ -f "venv/bin/python" ]; then
    PY_CMD="venv/bin/python"
    echo "[*] Using local virtual environment: venv"
elif command -v python3 >/dev/null 2>&1; then
    PY_CMD="python3"
    echo "[*] Using python3 ($(python3 --version))"
elif command -v python >/dev/null 2>&1; then
    PY_CMD="python"
    echo "[*] Using python ($(python --version))"
else
    echo "[!] ERROR: Python was not found on your system!"
    echo "Please install Python 3.10+ (via brew install python or miniconda/pyenv)."
    exit 1
fi

# 2. Check Python version >= 3.9
$PY_CMD -c '
import sys
if sys.version_info < (3, 9):
    print(f"[!] Warning: Python version {sys.version} may be too old. Recommended: 3.10+")
'

# 3. Check for essential packages (fastapi, uvicorn)
if ! $PY_CMD -c "import fastapi, uvicorn" >/dev/null 2>&1; then
    echo "[*] Required packages missing. Installing requirements from requirements.txt..."
    $PY_CMD -m pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "[!] Failed to install dependencies. Please run 'pip install -r requirements.txt' manually."
        exit 1
    fi
fi

# 4. Create .env from template if not present
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    echo "[*] No .env found. Creating .env from .env.example..."
    cp .env.example .env
fi

# 5. Start the server
echo ""
echo "[*] Launching CypherScreen web dashboard..."
echo "[*] Press Ctrl+C in this terminal to stop the server anytime."
echo ""

exec $PY_CMD -m backend.app "$@"
