@echo off
setlocal EnableDelayedExpansion
pushd "%~dp0"
echo STEP 1: Header
echo.
echo STEP 2: Before git check
if exist ".git" (
    echo STEP 3: Inside git block
    echo [*] Inside git block
)
echo STEP 4: After git block
echo.
echo SUCCESS
popd
