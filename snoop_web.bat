@echo off
setlocal
set SCRIPT_DIR=%~dp0
set SNOOP_EXE=%SCRIPT_DIR%snoop\.venv\Scripts\snoop.exe

if not exist "%SNOOP_EXE%" (
    echo [ERROR] Snoop virtual environment not found at:
    echo "%SNOOP_EXE%"
    pause
    exit /b 1
)

echo ============================================================
echo                   SNOOP WEB DASHBOARD
echo ============================================================
echo Starting Snoop Web Workspace on http://127.0.0.1:8005 ...
echo Opening your browser...
echo.
echo Press Ctrl+C in this window to stop the server.
echo ============================================================
echo.

start "" "http://127.0.0.1:8005"
"%SNOOP_EXE%" web --port 8005
