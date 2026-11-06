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

if not "%~1"=="" goto run_with_args

echo ============================================================
echo                     NUMINT PHONE OSINT
echo ============================================================
echo Look up a phone number and get an intelligence profile.
echo Example format: +14155550123 or +628123456789
echo.
set "PHONE_INPUT="
set /p PHONE_INPUT="Enter phone number (or --help): "
if "%PHONE_INPUT%"=="" (
    echo No phone number entered. Exiting.
    pause
    exit /b 0
)

"%NUMINT_EXE%" scan %PHONE_INPUT%
echo.
echo Search complete. Press any key to exit...
pause >nul
exit /b 0

:run_with_args
"%NUMINT_EXE%" %*
