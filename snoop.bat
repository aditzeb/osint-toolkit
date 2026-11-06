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

if not "%~1"=="" goto run_with_args

echo ============================================================
echo                   SNOOP PERSONA OSINT
echo ============================================================
echo Public profile footprint and evidence-backed investigation.
echo.
set "NAME_INPUT="
set /p NAME_INPUT="Enter target full name or handle (or --help): "
if "%NAME_INPUT%"=="" (
    echo No target entered. Exiting.
    pause
    exit /b 0
)

"%SNOOP_EXE%" "%NAME_INPUT%"
echo.
echo Investigation complete. Press any key to exit...
pause >nul
exit /b 0

:run_with_args
"%SNOOP_EXE%" %*
