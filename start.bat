@echo off
setlocal enabledelayedexpansion
title CypherScreen - Binance Market Screener ^& Bot
cd /d "%~dp0"

echo ======================================================================
echo    CYPHERSCREEN : Live Binance Market Screener ^& Trading Engine
echo ======================================================================
echo.

:: 1. Detect Python environment (.venv, venv, or PATH)
set "PY_CMD="
if exist ".venv\Scripts\python.exe" (
    set "PY_CMD=.venv\Scripts\python.exe"
    echo [*] Using local virtual environment: .venv
) else if exist "venv\Scripts\python.exe" (
    set "PY_CMD=venv\Scripts\python.exe"
    echo [*] Using local virtual environment: venv
) else (
    set "PY_CMD=python"
    echo [*] Using system Python
)

:: 2. Check if python works
%PY_CMD% --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [!] ERROR: Python was not found on your system!
    echo Please install Python 3.9 or higher and check "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

:: 3. Check for essential packages (fastapi, uvicorn)
%PY_CMD% -c "import fastapi, uvicorn" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [*] Required packages missing. Installing requirements from requirements.txt...
    %PY_CMD% -m pip install -r requirements.txt
    if %ERRORLEVEL% NEQ 0 (
        echo [!] Failed to install dependencies. Please run 'pip install -r requirements.txt' manually.
        pause
        exit /b 1
    )
)

:: 4. Start the server and launch the browser
echo.
echo [*] Starting web server at http://127.0.0.1:8000 ...
echo [*] Opening browser automatically...
echo [*] Press Ctrl+C in this window to stop the server anytime.
echo.

%PY_CMD% -m backend.app

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] Server stopped or encountered an error. (Exit code: %ERRORLEVEL%)
    pause
)
