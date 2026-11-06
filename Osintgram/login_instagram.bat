@echo off
setlocal
cd /d "%~dp0"
echo ============================================================
echo           OSINTGRAM: INSTAGRAM LOGIN (INSTAGRAPI)
echo ============================================================
echo Logging into Instagram to generate config\instagrapi_session.json
echo.
.\.venv\Scripts\python.exe scripts\instagrapi_login.py
echo.
pause

