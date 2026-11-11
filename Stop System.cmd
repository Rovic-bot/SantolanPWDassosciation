@echo off
cd /d "%~dp0"
if exist ".local\development\" (
    ".venv\Scripts\python.exe" -B scripts\current_development.py stop
) else (
    echo Press Ctrl+C in the Start System window to stop this checkout's server.
)
pause
