@echo off
setlocal EnableDelayedExpansion
title Synapic Build Installer

echo ===============================================================================
echo                          SYNAPIC BUILD INSTALLER                             
echo ===============================================================================
echo.

REM Get version from pyproject.toml
set "VERSION="
for /f "tokens=3 delims==," %%i in ('findstr /c:"version" pyproject.toml') do (
    set "VERSION=%%i"
    goto :version_found
)
:version_found

if defined VERSION (
    echo [*] Building Synapic v!VERSION!
) else (
    echo [!] Warning: Could not determine version from pyproject.toml, using default
    set VERSION=2.5.0
)

echo.
echo ===============================================================================
echo                          STEP 1: CLEANING BUILD                             
echo ===============================================================================
echo.

if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
echo [V] Cleaned build and dist directories

echo.
echo ===============================================================================
echo                       STEP 2: BUILDING APPLICATION                          
echo ===============================================================================
echo.

pyinstaller main.spec
if !errorlevel! neq 0 (
    echo [ERROR] PyInstaller build failed!
    pause
    exit /b 1
)

echo [V] Application built successfully

if not exist "dist\Synapic\Synapic.exe" (
    echo [ERROR] Synapic.exe not found in dist\Synapic\
    pause
    exit /b 1
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
    pause
    exit /b 1
)

if exist "Synapic-Setup.exe" (
    echo [V] Installer created: Synapic-Setup.exe
) else (
    echo [!] Warning: Installer executable not found
)

:back_to_build
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
