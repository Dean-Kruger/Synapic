@echo off
setlocal EnableDelayedExpansion
if exist ".git" (
    where gh >nul 2>&1
    if !errorlevel! neq 0 (
        echo Installing gh
        winget install -e --id GitHub.cli --source winget --accept-package-agreements --accept-source-agreements >nul 2>&1
    )
    where gh >nul 2>&1
    if !errorlevel! equ 0 (
        git fetch origin main >nul 2>&1
        if !errorlevel! equ 0 (
            for /f %%i in ('git rev-list --count HEAD..origin/main 2^>nul') do set BEHIND=%%i
            if defined BEHIND (
                if !BEHIND! gtr 0 (
                    echo You are !BEHIND! commit(s) behind
                ) else (
                    echo Latest version
                )
            )
        )
    )
)
echo SUCCESS
