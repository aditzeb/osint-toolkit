@echo off
setlocal
set SCRIPT_DIR=%~dp0
set HOLEHE_EXE=%SCRIPT_DIR%holehe\.venv\Scripts\holehe.exe

if not exist "%HOLEHE_EXE%" (
    echo [ERROR] Holehe virtual environment not found at:
    echo "%HOLEHE_EXE%"
    pause
    exit /b 1
)

if not "%~1"=="" goto run_with_args

echo ============================================================
echo                  HOLEHE EMAIL OSINT (120+ SITES)
echo ============================================================
echo Check which platforms an email address is registered on.
echo.
set "EMAIL_INPUT="
set /p EMAIL_INPUT="Enter target email address (or --help): "
if "%EMAIL_INPUT%"=="" (
    echo No email entered. Exiting.
    pause
    exit /b 0
)

"%HOLEHE_EXE%" --only-used %EMAIL_INPUT%
echo.
echo Scan complete. Press any key to exit...
pause >nul
exit /b 0

:run_with_args
"%HOLEHE_EXE%" %*
