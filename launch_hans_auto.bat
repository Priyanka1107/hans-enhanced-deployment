@echo off
REM Automated HANS Launcher for Windows
REM Handles tunnel + GUI automatically

setlocal enabledelayedexpansion

REM Configuration
set SERVER_USER=aleks
set SERVER_HOST=10.2.100.35
set SERVER_PORT=22
set LOCAL_PORT=8080
set REMOTE_PORT=8080

REM Get script directory
set SCRIPT_DIR=%~dp0

echo ================================================================
echo    HANS - HTW Berlin Student Services Assistant
echo ================================================================
echo.

REM Check if GUI file exists
if not exist "%SCRIPT_DIR%htw_assistant_api_gui.py" (
    echo ERROR: htw_assistant_api_gui.py not found in %SCRIPT_DIR%
    echo Please ensure the GUI file is in the same directory as this script.
    pause
    exit /b 1
)

REM Check if Python is installed
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8 or higher first.
    pause
    exit /b 1
)

REM Check if SSH is available
where ssh >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: SSH client not found
    echo.
    echo Windows 10/11 includes OpenSSH. To enable it:
    echo   1. Settings ^> Apps ^> Optional Features
    echo   2. Add "OpenSSH Client"
    echo   3. Restart this script
    echo.
    pause
    exit /b 1
)

REM Check if requests module is installed
python -c "import requests" 2>nul
if %errorlevel% neq 0 (
    echo Warning: 'requests' module not found
    echo Installing requests module...
    pip install requests
    if %errorlevel% neq 0 (
        echo ERROR: Failed to install requests
        echo Please run: pip install requests
        pause
        exit /b 1
    )
)

echo Step 1: Establishing SSH tunnel to HANS server...
echo Server: %SERVER_USER%@%SERVER_HOST%:%SERVER_PORT%
echo You will be prompted for your SSH password.
echo.

REM Start SSH tunnel in background
start /B ssh -N -L %LOCAL_PORT%:127.0.0.1:%REMOTE_PORT% -o ServerAliveInterval=60 -o ServerAliveCountMax=3 %SERVER_USER%@%SERVER_HOST% -p %SERVER_PORT%

if %errorlevel% neq 0 (
    echo ERROR: Failed to start SSH tunnel
    echo.
    echo Common issues:
    echo   - Incorrect password
    echo   - Not connected to HTW network/VPN
    echo   - Server unreachable
    echo.
    pause
    exit /b 1
)

REM Wait for tunnel to establish
echo Waiting for tunnel to establish...
timeout /t 5 /nobreak >nul

REM Test API connection
echo.
echo Step 2: Testing connection to HANS API...
curl -s -m 5 http://127.0.0.1:%LOCAL_PORT%/health >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] HANS API is responding
) else (
    echo [WARNING] API connection test failed
    echo The GUI may show a connection error. Ensure HANS API is running on the server.
)

echo.
echo Step 3: Launching HANS GUI...
echo.

REM Launch GUI (blocks until GUI closes)
cd /d "%SCRIPT_DIR%"
python htw_assistant_api_gui.py

REM When GUI closes, kill the tunnel
echo.
echo Closing SSH tunnel...
taskkill /F /IM ssh.exe >nul 2>&1

echo.
echo HANS closed. Have a great day!
echo.
pause
