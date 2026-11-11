@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" -B scripts\ewaf_twelve_demo.py start
if errorlevel 1 (
  echo.
  echo The separate EWAF demo could not start. The normal system was not changed.
)
pause
