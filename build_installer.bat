@echo off
setlocal EnableDelayedExpansion
title Synapic Build Installer

REM ===============================================================================
REM Usage: build_installer.bat [/silent | /ci]
REM   /silent, /ci   Skip all "pause" prompts (also auto-enabled when %CI% is set)
REM Exit codes: 0 = success, 1 = failure (safe to check in CI pipelines)
REM ===============================================================================

set "SILENT=0"
if /i "%~1"=="/silent" set "SILENT=1"
if /i "%~1"=="/ci" set "SILENT=1"
if defined CI set "SILENT=1"

echo ===============================================================================
echo                          SYNAPIC BUILD INSTALLER
echo ===============================================================================
echo.

if "%SILENT%"=="1" (
    echo [*] Running in silent/CI mode - prompts will be skipped
    echo.
)

echo ===============================================================================
echo                       STEP 0: PRE-FLIGHT CHECKS
echo ===============================================================================
echo.

if not exist "pyproject.toml" (
    echo [ERROR] pyproject.toml not found. Run this script from the repository root.
    goto :fail
)

if not exist "main.spec" (
    echo [ERROR] main.spec not found. Run this script from the repository root.
    goto :fail
)

where pyinstaller >nul 2>&1
if !errorlevel! neq 0 (
    echo [ERROR] pyinstaller not found on PATH. Install it with: pip install pyinstaller
    goto :fail
)

echo [V] Pre-flight checks passed

echo.
echo ===============================================================================
echo                       DETECTING VERSION
echo ===============================================================================
echo.

REM Only match a line that STARTS WITH "version" (avoids matching
REM "minversion" / "python_version" elsewhere in pyproject.toml), then split on
REM the quote character to pull out the value between the quotes.
set "VERSION="
for /f "tokens=2 delims=""" %%v in ('findstr /b /c:"version" pyproject.toml') do (
    if not defined VERSION set "VERSION=%%v"
)

if defined VERSION (
    echo [*] Building Synapic v!VERSION!
) else (
    echo [!] Warning: Could not determine version from pyproject.toml, using default
    set "VERSION=2.5.0"
)

echo.
echo ===============================================================================
echo                          STEP 1: CLEANING BUILD
echo ===============================================================================
echo.

if exist "build" (
    rmdir /s /q "build"
    if exist "build" (
        echo [ERROR] Failed to remove existing "build" directory. Close any programs using it and retry.
        goto :fail
    )
)
if exist "dist" (
    rmdir /s /q "dist"
    if exist "dist" (
        echo [ERROR] Failed to remove existing "dist" directory. Close any programs using it and retry.
        goto :fail
    )
)
echo [V] Cleaned build and dist directories

echo.
echo ===============================================================================
echo                       STEP 2: BUILDING APPLICATION
echo ===============================================================================
echo.

pyinstaller main.spec
if !errorlevel! neq 0 (
    echo [ERROR] PyInstaller build failed!
    goto :fail
)

echo [V] Application built successfully

if not exist "dist\Synapic\Synapic.exe" (
    echo [ERROR] Synapic.exe not found in dist\Synapic\
    goto :fail
)

echo.
echo ===============================================================================
echo                        STEP 3: BUILDING INSTALLER
echo ===============================================================================
echo.

REM Check for NSIS (makensis.exe)
where makensis.exe >nul 2>&1
if !errorlevel! neq 0 (
    echo [!] NSIS not found in PATH.
    echo [*] Please install NSIS from https://nsis.sourceforge.io/
    echo [*] Or add it to your PATH environment variable
    echo.
    echo [!] Building application only (without installer)
    echo.
    goto :build_complete
)

echo [*] NSIS found, building installer...

REM Build the installer with version info
makensis /DVERSION=!VERSION! installer.nsi
if !errorlevel! neq 0 (
    echo [ERROR] NSIS installer build failed!
    goto :fail
)

if not exist "Synapic-Setup.exe" (
    echo [!] Warning: Installer executable not found
)

echo.
echo ===============================================================================
echo                          BUILD COMPLETE
echo ===============================================================================
echo.

if exist "dist\Synapic\Synapic.exe" (
    echo [*] Application executable: dist\Synapic\Synapic.exe
)
if exist "Synapic-Setup.exe" (
    echo [*] Installer executable: Synapic-Setup.exe
)
echo.
echo [V] Build complete!
echo.

exit /b 0

:build_complete
echo.
echo [*] Application built but installer not created (NSIS not available)
echo.
exit /b 0

:fail
echo.
echo ===============================================================================
echo                          BUILD FAILED
echo ===============================================================================
if "%SILENT%"=="0" pause
exit /b 1
