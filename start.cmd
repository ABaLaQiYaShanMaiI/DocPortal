@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"

echo =============================================
echo  FolderKnowledgeSiteGeneratorForAI
echo =============================================
echo.

REM -- Step 1: Quick Python check --
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.8+.
    pause
    exit /b 1
)
echo [OK] Python detected.

REM -- Step 2: Virtual environment (only on first run) --
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo [WARN] venv failed. Running without venv.
        goto :quick_check
    )
)
call ".venv\Scripts\activate.bat" >nul 2>&1
if errorlevel 1 goto :quick_check
echo [OK] Venv active.

:quick_check
REM -- Step 3: Fast dependency check (skip pip if already verified) --
set MARKER=.venv\deps_ok.marker
if not exist ".venv" set MARKER=.\deps_ok.marker
if exist "%MARKER%" (
    echo [OK] Dependencies verified. Starting GUI...
    goto :launch
)

echo Installing dependencies (first run)...
pip install -r requirements.txt --quiet 2>&1
if errorlevel 1 (
    echo [WARN] Some deps failed. Retrying...
    pip install -r requirements.txt
)

REM -- Windows: python-magic-bin --
pip show python-magic-bin >nul 2>&1 || pip install python-magic-bin --quiet 2>&1

REM -- Optional: tkinterdnd2 (one-shot check via Python, no pip overhead) --
echo Checking drag-and-drop support...
python -c "import tkinterdnd2" 2>nul && echo    [OK] Drag-and-drop ready || (
    echo    Installing tkinterdnd2...
    pip install tkinterdnd2 --quiet 2>&1 && (
        python -c "import tkinterdnd2" 2>nul && echo    [OK] Drag-and-drop ready || echo    [WARN] tkinterdnd2 import failed
    ) || echo    [INFO] Drag-and-drop unavailable. Use Browse/Paste instead.
)

REM -- Mark deps as verified so next launch skips pip --
echo verified > "%MARKER%"

:launch
echo.
echo Starting GUI...
echo -----------------------------------------
python gui.py 2>&1
set GUI_EXIT_CODE=%errorlevel%
echo -----------------------------------------

if %GUI_EXIT_CODE% neq 0 (
    del "%MARKER%" 2>nul
    echo.
    echo [ERROR] GUI crashed (exit code: %GUI_EXIT_CODE%).
    echo   1. Try: pip install -r requirements.txt
    echo   2. Try: python gui.py  (directly)
    pause
)