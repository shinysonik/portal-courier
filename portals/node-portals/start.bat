@echo off
setlocal enabledelayedexpansion
title Mock Supplier Portals - Zero-Trust Testbed
cd /d "%~dp0"

:: 1. WinGet / System PATH check for node
where node >nul 2>&1
if %errorlevel% neq 0 (
    set "WINGET_NODE=%LOCALAPPDATA%\Microsoft\WinGet\Packages\OpenJS.NodeJS.LTS_Microsoft.Winget.Source_8wekyb3d8bbwe\node-v24.19.0-win-x64"
    if exist "!WINGET_NODE!\node.exe" (
        set "PATH=!WINGET_NODE!;%PATH%"
    )
)

where node >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] ERROR: Node.js was not found in PATH or WinGet location.
    echo     Please verify Node.js installation.
    echo.
    pause
    exit /b 1
)

echo ==================================================================
echo   Mock Supplier Portals ^& Autonomous Agent Testbed
echo   Portals Directory: http://localhost:3000/
echo   Agent Dashboard:   dashboard.html
echo ==================================================================
echo [*] Launching portals in browser...

:: Launch browser tabs in background after 800ms delay so server binds first
start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Milliseconds 800; Start-Process 'http://localhost:3000/'; Start-Process '%~dp0dashboard.html'"

:: Run server in foreground keeping this terminal window open with live request logs
node server.js
if %errorlevel% neq 0 (
    echo.
    echo [!] Server exited with code: %errorlevel%
    pause
)
