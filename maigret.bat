@echo off
setlocal
set SCRIPT_DIR=%~dp0
set MAIGRET_EXE=%SCRIPT_DIR%maigret\.venv\Scripts\maigret.exe

if not exist "%MAIGRET_EXE%" (
    echo [ERROR] Maigret virtual environment not found at:
    echo "%MAIGRET_EXE%"
    pause
    exit /b 1
)

if not "%~1"=="" goto run_with_args

echo ============================================================
echo                     MAIGRET OSINT
echo ============================================================
echo Collect a dossier by username from 5,900+ sites.
echo.
set "USERNAME_INPUT="
set /p USERNAME_INPUT="Enter username to search (or --help / --web): "
if "%USERNAME_INPUT%"=="" (
    echo No username entered. Exiting.
    pause
    exit /b 0
)

"%MAIGRET_EXE%" %USERNAME_INPUT%
echo.
echo Done. Press any key to exit...
pause >nul
exit /b 0

:run_with_args
"%MAIGRET_EXE%" %*
