@echo off
setlocal
cd /d "%~dp0"
echo ============================================================
echo       OSINTGRAM: LOGIN VIA BROWSER SESSION ID
echo ============================================================
echo Bypass Instagram bot detection and challenges by using your browser's session.
echo.
.\.venv\Scripts\python.exe scripts\set_session.py %*
echo.
pause

