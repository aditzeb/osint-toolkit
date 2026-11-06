@echo off
setlocal
set SCRIPT_DIR=%~dp0
set OSINTGRAM_DIR=%SCRIPT_DIR%Osintgram
set UVICORN_EXE=%OSINTGRAM_DIR%\.venv\Scripts\uvicorn.exe

if not exist "%UVICORN_EXE%" (
    echo [ERROR] Osintgram virtual environment not found at:
    echo "%UVICORN_EXE%"
    pause
    exit /b 1
)

echo ============================================================
echo                    OSINTGRAM WEB INTERFACE
echo ============================================================
echo Starting Osintgram server at http://127.0.0.1:8000 ...
echo Opening your default browser...
echo.
echo Press Ctrl+C in this window to stop the server.
echo ============================================================
echo.

cd /d "%OSINTGRAM_DIR%"
start "" "http://127.0.0.1:8000"
"%UVICORN_EXE%" src.web.app:app --host 127.0.0.1 --port 8000 --reload

