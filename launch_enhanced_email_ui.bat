@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Could not find .venv\Scripts\python.exe
    pause
    exit /b 1
)

".venv\Scripts\python.exe" enhanced_email_ui.py
