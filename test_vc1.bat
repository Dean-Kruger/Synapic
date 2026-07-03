@echo off
setlocal EnableDelayedExpansion
REM --- 0.5 Update Check via GitHub CLI ---
if exist ".git" (
    echo [*] Checking for updates...
    set "_SKIP_UPDATE="

    REM Check/Install GitHub CLI
    where gh >nul 2>&1
    if !errorlevel! neq 0 (
        echo [!] GitHub CLI not found. Attempting to install...
        where winget >nul 2>&1
        if !errorlevel! equ 0 (
            winget install -e --id GitHub.cli --source winget --accept-package-agreements --accept-source-agreements >nul 2>&1
echo SUCCESS
