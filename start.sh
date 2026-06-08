#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================="
echo " FolderKnowledgeSiteGeneratorForAI"
echo "============================================="
echo ""

# -- Step 1: Quick Python check --
PYTHON_CMD=()
if command -v python3 &>/dev/null && python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" 2>/dev/null; then
    PYTHON_CMD=(python3)
elif command -v python &>/dev/null && python -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" 2>/dev/null; then
    PYTHON_CMD=(python)
else
    echo "[ERROR] Python 3.8+ not found."
    echo "Install: https://www.python.org/downloads/"
    exit 1
fi
echo "[OK] Python detected: $("${PYTHON_CMD[@]}" --version)"

# -- Step 2: Virtual environment (only on first run) --
HAS_VENV=0
if [ -f ".venv/bin/activate" ]; then
    source ".venv/bin/activate"
    PYTHON=("$SCRIPT_DIR/.venv/bin/python")
    HAS_VENV=1
elif [ -f ".venv/Scripts/activate" ]; then
    source ".venv/Scripts/activate"
    PYTHON=("$SCRIPT_DIR/.venv/Scripts/python.exe")
    HAS_VENV=1
else
    PYTHON=("${PYTHON_CMD[@]}")
fi

if [ "$HAS_VENV" -eq 0 ] && [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    "${PYTHON_CMD[@]}" -m venv .venv 2>/dev/null && {
        if [ -f ".venv/bin/activate" ]; then
            source ".venv/bin/activate"
            PYTHON=("$SCRIPT_DIR/.venv/bin/python")
        elif [ -f ".venv/Scripts/activate" ]; then
            source ".venv/Scripts/activate"
            PYTHON=("$SCRIPT_DIR/.venv/Scripts/python.exe")
        fi
    } || echo "  [WARN] venv failed, running without."
fi
echo "[OK] Python runtime: $("${PYTHON[@]}" --version)"

# -- Step 3: Fast dependency check (skip if already verified) --
MARKER=".venv/deps_ok.marker"
[ -d ".venv" ] || MARKER="./deps_ok.marker"

if [ -f "$MARKER" ]; then
    echo "[OK] Dependencies verified. Skipping pip install."
else
    echo "Installing dependencies (first run)..."
    "${PYTHON[@]}" -m pip install -r requirements.txt --quiet 2>&1 || {
        echo "  [WARN] Some deps failed. Retrying..."
        "${PYTHON[@]}" -m pip install -r requirements.txt
    }

    # -- Optional: tkinterdnd2 (one-shot check via Python) --
    echo "Checking drag-and-drop support..."
    if "${PYTHON[@]}" -c "import tkinterdnd2" 2>/dev/null; then
        echo "  [OK] Drag-and-drop ready"
    else
        echo "  Installing tkinterdnd2..."
        "${PYTHON[@]}" -m pip install tkinterdnd2 --quiet 2>&1 && {
            if "${PYTHON[@]}" -c "import tkinterdnd2" 2>/dev/null; then
                echo "  [OK] Drag-and-drop ready"
            else
                echo "  [WARN] tkinterdnd2 import failed — drag disabled"
            fi
        } || echo "  [INFO] Drag-and-drop unavailable. Use Browse/Paste instead."
    fi

    # -- Verify tkinter --
    if ! "${PYTHON[@]}" -c "import tkinter" 2>/dev/null; then
        echo "  [ERROR] tkinter is not installed!"
        echo "  Ubuntu: sudo apt-get install python3-tk"
        echo "  Fedora: sudo dnf install python3-tkinter"
        echo "  macOS:  brew install python-tk"
        exit 1
    fi
    echo "  [OK] tkinter ready"

    # Mark as verified
    echo "verified" > "$MARKER"
fi

echo ""
echo "Starting GUI..."
echo "-----------------------------------------"
"${PYTHON[@]}" gui.py
GUIRC=$?
echo "-----------------------------------------"

if [ $GUIRC -ne 0 ]; then
    rm -f "$MARKER"
    echo "[ERROR] GUI crashed (exit code: $GUIRC)."
    echo "  Try: pip install -r requirements.txt"
    echo "  Try: python gui.py"
    read -p "Press Enter to exit..."
fi