@echo off
setlocal
set SCRIPT_DIR=%~dp0
set SHERLOCK_EXE=%SCRIPT_DIR%sherlock\.venv\Scripts\sherlock.exe

if not exist "%SHERLOCK_EXE%" (
    echo [ERROR] Sherlock virtual environment not found at:
    echo "%SHERLOCK_EXE%"
    pause
    exit /b 1
)

if not "%~1"=="" goto run_with_args

echo ============================================================
echo                     SHERLOCK OSINT
echo ============================================================
echo Hunt down social media accounts by username across 400+ platforms.
echo.
set "USERNAME_INPUT="
set /p USERNAME_INPUT="Enter username to search (or --help): "
if "%USERNAME_INPUT%"=="" (
    echo No username entered. Exiting.
    pause
    exit /b 0
)

"%SHERLOCK_EXE%" %USERNAME_INPUT%
echo.
echo Search complete. Press any key to exit...
pause >nul
exit /b 0

:run_with_args
"%SHERLOCK_EXE%" %*
