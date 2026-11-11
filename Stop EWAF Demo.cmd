@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" -B scripts\ewaf_twelve_demo.py stop
pause
