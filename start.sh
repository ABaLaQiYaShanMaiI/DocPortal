 #!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================="
echo " FolderKnowledgeSiteGeneratorForAI"
echo " Document Knowledge Portal Generator"
echo "============================================="
echo ""

# -- Step 1: Check Python --
if ! command -v python3 &>/dev/null; then
    echo "[ERROR] Python 3 not found."
    echo "Please install Python 3.8+ from https://www.python.org/downloads/"
    if command -v brew &>/dev/null; then
        echo "Or run: brew install python3"
    fi
    if command -v apt-get &>/dev/null; then
        echo "Or run: sudo apt-get install python3 python3-venv python3-tk"
    fi
    read -p "Press Enter to exit..."
    exit 1
fi
echo "[OK] Python detected: $(python3 --version)"

# -- Step 2: Check/create virtual environment --
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv || {
        echo "[WARN] Failed to create venv. Running without venv."
        PIP="pip3"
        PYTHON="python3"
        HAS_VENV=0
    }
fi

if [ -z "$HAS_VENV" ]; then
    source ".venv/bin/activate" 2>/dev/null || true
    echo "[OK] Virtual environment active."
    PIP="pip"
    PYTHON="python"
else
    PIP="pip3"
    PYTHON="python3"
fi

# -- Step 3: Install dependencies --
echo "Checking dependencies..."
$PIP install -r requirements.txt --quiet 2>&1 || {
    echo "[WARN] Some dependencies failed. Retrying with output..."
    $PIP install -r requirements.txt
}

# -- Optional: tkinterdnd2 for drag-and-drop --
$PIP show tkinterdnd2 >/dev/null 2>&1 || {
    echo "Installing tkinterdnd2 (drag-and-drop support)..."
    $PIP install tkinterdnd2 --quiet 2>&1 || echo "  [WARN] tkinterdnd2 not available."
}

echo ""
echo "Starting GUI..."
echo ""
$PYTHON gui.py || {
    echo ""
    echo "[ERROR] Failed to start GUI."
    echo "Make sure Python 3 and tkinter are installed."
    read -p "Press Enter to exit..."
}