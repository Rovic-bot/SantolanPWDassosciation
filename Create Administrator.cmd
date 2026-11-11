@echo off
cd /d "%~dp0"
echo Create your real administrator for the fresh local development database.
echo Django will ask for a username, email address, and a hidden password.
".venv\Scripts\python.exe" manage.py createsuperuser
pause
