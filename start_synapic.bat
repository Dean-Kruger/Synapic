@echo off
setlocal EnableDelayedExpansion
title Synapic Launcher
color 0A

echo ===============================================================================
echo                                SYNAPIC LAUNCHER                                
echo ===============================================================================
echo.

:: 1. Check for Python
echo [*] Checking for Python installation...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Python is NOT found. Attempting to install...
    
    :: Check if winget is available
    where winget >nul 2>&1
    if !errorlevel! neq 0 (
        color 0C
        echo [ERROR] Winget is not available to auto-install Python.
        echo Please install Python manually from https://www.python.org/
        pause
        exit /b 1
    )

    echo [*] Installing Python via Winget...
    winget install -e --id Python.Python.3 --source winget --accept-package-agreements --accept-source-agreements
    
    if !errorlevel! neq 0 (
        color 0C
        echo [ERROR] Automatic installation failed.
        echo Please install Python manually from https://www.python.org/
        pause
        exit /b 1
    )
    
    echo [*] Python installed.
    echo [!] IMPORTANT: You may need to restart this script or your terminal to pick up the new PATH.
    pause
    exit /b 0
) else (
    echo [V] Python is installed:
    python --version
)

echo.
echo ===============================================================================
echo                          SETTING UP ENVIRONMENT                                
echo ===============================================================================
echo.

:: 2. Setup/Check Virtual Environment
if not exist ".venv" (
    echo [*] Creating virtual environment .venv...
    python -m venv .venv
    if !errorlevel! neq 0 (
        echo [!] Failed to create venv. Will attempt to use system Python...
    ) else (
        echo [V] Virtual environment created.
    )
)

if exist ".venv" (
    echo [*] Activating virtual environment...
    if exist ".venv\Scripts\activate.bat" (
        call .venv\Scripts\activate.bat
        echo [V] Virtual environment activated.
    ) else (
        echo [!] .venv folder exists but activate.bat not found. Using system Python.
    )
)

:: 3. Install Requirements
echo.
echo [*] Checking dependencies...
if exist "requirements.txt" (
    echo [*] Installing/Updating requirements...
    pip install -r requirements.txt
    if !errorlevel! neq 0 (
        color 0C
        echo.
        echo [ERROR] Failed to install dependencies.
        echo Please check your internet connection or requirements.txt file.
        pause
        exit /b 1
    )
    echo [V] Dependencies installed/updated.
) else (
    echo [!] requirements.txt not found! Skipping dependency installation.
)

echo.
echo ===============================================================================
echo                               LAUNCHING APP                                    
echo ===============================================================================
echo.

:: 4. Launch Main
if exist "main.py" (
    echo [*] Launching application...
    start "" pythonw "main.py"
) else (
    color 0C
    echo [ERROR] main.py not found in current directory!
    pause
    exit /b 1
)

endlocal
