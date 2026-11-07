@echo off
cd /d "%~dp0"
title Mock Supplier Portals
where node >nul 2>&1
if %errorlevel% neq 0 (
    if exist "%LOCALAPPDATA%\Microsoft\WinGet\Packages\OpenJS.NodeJS.LTS_Microsoft.Winget.Source_8wekyb3d8bbwe\node-v24.19.0-win-x64\node.exe" (
        set "PATH=%LOCALAPPDATA%\Microsoft\WinGet\Packages\OpenJS.NodeJS.LTS_Microsoft.Winget.Source_8wekyb3d8bbwe\node-v24.19.0-win-x64;%PATH%"
    )
)
echo ==================================================================
echo   Starting Mock Supplier Portals...
echo ==================================================================
node server.js
if %errorlevel% neq 0 (
    echo [!] Server exited with error code %errorlevel%
    pause
)