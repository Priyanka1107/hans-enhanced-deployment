@echo off
REM SSH Tunnel Setup for HANS GUI (Windows)
REM This script creates an SSH tunnel to the HTW server

setlocal enabledelayedexpansion

REM ============================================================================
REM CONFIGURATION - UPDATE THESE VALUES
REM ============================================================================

set SERVER_USER=your-username
set SERVER_HOST=hans-server.htw-berlin.de
set SERVER_PORT=22
set REMOTE_PORT=8080
set LOCAL_PORT=8080

REM ============================================================================

echo ================================================================
echo        HANS SSH Tunnel Connection Manager (Windows)
echo ================================================================
echo.

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

echo Connection Details:
echo   Server: %SERVER_USER%@%SERVER_HOST%:%SERVER_PORT%
echo   Remote API: 127.0.0.1:%REMOTE_PORT%
echo   Local Port: %LOCAL_PORT%
echo.
echo Creating SSH tunnel...
echo.

REM Create SSH tunnel
ssh -N -L %LOCAL_PORT%:127.0.0.1:%REMOTE_PORT% -o ServerAliveInterval=60 -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes %SERVER_USER%@%SERVER_HOST% -p %SERVER_PORT%

if %errorlevel% equ 0 (
    echo.
    echo ================================================================
    echo   Tunnel is ACTIVE - You can now run the HANS GUI
    echo ================================================================
    echo.
    echo   HANS API is now available at: http://localhost:%LOCAL_PORT%
    echo.
    echo Next steps:
    echo   1. Open a new Command Prompt
    if not "%LOCAL_PORT%"=="8080" (
        echo   2. Run: set HANS_API_BASE=http://127.0.0.1:%LOCAL_PORT%
        echo   3. Run: python htw_assistant_api_gui.py
    ) else (
        echo   2. Run: python htw_assistant_api_gui.py
    )
    echo.
    echo Press Ctrl+C to close this tunnel
    echo.
) else (
    echo.
    echo ERROR: Failed to establish SSH tunnel
    echo.
    echo Common issues:
    echo   - Check username and hostname are correct
    echo   - Verify you can SSH to the server: ssh %SERVER_USER%@%SERVER_HOST%
    echo   - Check if SSH key authentication is set up
    echo   - Verify the server is reachable from your network
    echo.
    pause
    exit /b 1
)

pause
