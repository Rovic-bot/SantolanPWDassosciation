@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" -B manage.py createsuperuser
pause
