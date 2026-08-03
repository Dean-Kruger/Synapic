@echo off
setlocal EnableDelayedExpansion
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
            if !errorlevel! equ 0 (
                echo [V] GitHub CLI installed.
                REM Refresh PATH — use separate if-exist checks to avoid for-loop
                REM parsing issues with %ProgramFiles% containing parentheses.
                if exist "%ProgramFiles%\GitHub CLI\gh.exe" (
                    set "PATH=%ProgramFiles%\GitHub CLI;%PATH%"
                )
                if exist "%LocalAppData%\GitHub CLI\gh.exe" (
                    set "PATH=%LocalAppData%\GitHub CLI;%PATH%"
                )
            ) else (
                echo [WARN] Failed to install GitHub CLI.
            )
        ) else (
            echo [WARN] Winget not available. Cannot install GitHub CLI.
        )
        REM Check again after installation attempt
        where gh >nul 2>&1
        if !errorlevel! neq 0 (
            echo [WARN] GitHub CLI still not found. Skipping version check.
            set "_SKIP_UPDATE=1"
        )
    )

    REM Verify authentication (required for private repos)
    if not defined _SKIP_UPDATE (
        gh auth status >nul 2>&1
        if !errorlevel! neq 0 (
            echo [WARN] GitHub CLI not authenticated. Run "gh auth login" manually.
            echo [WARN] Skipping version check.
            set "_SKIP_UPDATE=1"
        ) else (
            echo [V] GitHub CLI authenticated.
        )
    )

    REM Fetch latest remote refs and compare
    if not defined _SKIP_UPDATE (
        git fetch origin main >nul 2>&1
        if !errorlevel! neq 0 (
            echo [WARN] Could not fetch latest version (check internet connection).
            echo [WARN] Skipping update check.
            set "_SKIP_UPDATE=1"
        )
    )

    if not defined _SKIP_UPDATE (
        git rev-list --count HEAD..origin/main 2>nul > "%TEMP%\synapic_behind.txt"
        set /p _BEHIND=<"%TEMP%\synapic_behind.txt"
        del "%TEMP%\synapic_behind.txt" 2>nul

        if not defined _BEHIND set _BEHIND=0

        if !_BEHIND! gtr 0 (
            echo [!] You are !_BEHIND! commit(s) behind the latest version.
            echo.
            choice /c YN /t 10 /d Y /n /m "Update now (Y/N, auto-pull in 10s)? "
            if !errorlevel! equ 1 (
                echo [*] Pulling latest changes...
                git pull origin main
                if !errorlevel! neq 0 (
                    echo [ERROR] Failed to pull latest changes.
                ) else (
                    echo [V] Updated to latest version.
                )
            ) else (
                echo [*] Update skipped.
            )
        ) else (
            echo [V] You are running the latest version.
        )
    )
) else (
    echo [*] Not a git repository - skipping version check.
    echo [*] Clone the repo from https://github.com/deanable/Synapic to enable updates.
)
echo.
echo SUCCESS - version check completed
