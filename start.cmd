@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"

echo =============================================
echo  FolderKnowledgeSiteGeneratorForAI
echo  Document Knowledge Portal Generator
echo =============================================
echo.

REM -- Step 1: Check Python --
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found.
    echo.
    echo Trying to install via winget...
    winget install Python.Python.3.12 --accept-source-agreements --accept-package-agreements >nul 2>&1
    if errorlevel 1 (
        echo Failed to install Python automatically.
        echo Please install Python 3.8+ from https://www.python.org/downloads/
        echo Make sure to check "Add Python to PATH" during installation.
        pause
        exit /b 1
    )
    echo Python installed. Please restart this script.
    pause
    exit /b 0
)

echo [OK] Python detected.

REM -- Step 2: Check/create virtual environment --
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create venv. Trying without venv...
        goto :skip_venv
    )
)
call ".venv\Scripts\activate.bat" >nul 2>&1
if errorlevel 1 goto :skip_venv
echo [OK] Virtual environment active.
goto :install_deps

:skip_venv
echo [WARN] Running without virtual environment.

:install_deps
REM -- Step 3: Install/update dependencies --
echo Checking dependencies...
pip install -r requirements.txt --quiet 2>&1
if errorlevel 1 (
    echo [WARN] Some dependencies failed. Retrying with output...
    pip install -r requirements.txt
)

REM -- Windows-specific: python-magic needs the -bin variant --
pip show python-magic-bin >nul 2>&1
if errorlevel 1 (
    echo Installing Windows-specific python-magic-bin...
    pip install python-magic-bin --quiet 2>&1
)

REM -- Optional: tkinterdnd2 for drag-and-drop --
pip show tkinterdnd2 >nul 2>&1
if errorlevel 1 (
    echo Installing tkinterdnd2 (drag-and-drop support)...
    pip install tkinterdnd2 --quiet 2>&1
    if errorlevel 1 echo   [WARN] tkinterdnd2 not available. Drag-and-drop disabled.
)

echo.
echo Starting GUI...
echo.
python gui.py
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to start GUI.
    echo Try running: pip install -r requirements.txt
    pause
)