@echo off
setlocal
set SCRIPT_DIR=%~dp0
set NUMINT_EXE=%SCRIPT_DIR%numint\.venv\Scripts\numint.exe

if not exist "%NUMINT_EXE%" (
    echo [ERROR] Numint virtual environment not found at:
    echo "%NUMINT_EXE%"
    pause
    exit /b 1
)

echo ============================================================
echo                   NUMINT WEB DASHBOARD
echo ============================================================
echo Starting Numint Web Server on http://127.0.0.1:8080 ...
echo Opening your browser...
echo.
echo Press Ctrl+C in this window to stop the server.
echo ============================================================
echo.

start "" "http://127.0.0.1:8080"
"%NUMINT_EXE%" web --port 8080
