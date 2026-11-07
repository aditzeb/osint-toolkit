@echo off
setlocal
title OSINT Toolkit - All-in-One Master Launcher (Windows 11)

cd /d "%~dp0"
set "ROOT_DIR=%~dp0"

:: 1. Verify Python installation
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo ======================================================================
    echo [ERROR] Python is not installed or not found in your system PATH.
    echo Please install Python 3.11+ from https://www.python.org/downloads/
    echo or run in Windows Terminal: winget install Python.Python.3.13
    echo ======================================================================
    pause
    exit /b 1
)

:: 2. Check for explicit setup command
if /i "%~1"=="setup" goto do_setup
if /i "%~1"=="--setup" goto do_setup

:: 3. Check if first-time setup is needed
if not exist "%ROOT_DIR%sherlock\.venv" goto prompt_first_setup
if not exist "%ROOT_DIR%maigret\.venv" goto prompt_first_setup
if not exist "%ROOT_DIR%Osintgram\.venv" goto prompt_first_setup
if not exist "%ROOT_DIR%numint\.venv" goto prompt_first_setup
if not exist "%ROOT_DIR%snoop\.venv" goto prompt_first_setup
if not exist "%ROOT_DIR%holehe\.venv" goto prompt_first_setup
if not exist "%ROOT_DIR%GHunt\.venv" goto prompt_first_setup
goto run_app

:prompt_first_setup
echo ======================================================================
echo              FIRST-TIME SETUP DETECTED FOR OSINT TOOLKIT
echo ======================================================================
echo One or more tool virtual environments (.venv) have not been created yet.
echo Would you like to run the automated setup now to install everything?
echo.
set /p DO_INIT="Run automated setup now? (Y/N) [default: Y]: "
if /i "%DO_INIT%"=="n" goto run_app

:do_setup
cls
echo ======================================================================
echo                 OSINT TOOLKIT - AUTOMATED SETUP
echo   Sherlock ^| Maigret ^| Osintgram ^| Numint ^| Snoop ^| Holehe ^| GHunt ^| ID
echo ======================================================================
echo.
python "%ROOT_DIR%app.py" --setup
if %errorlevel% neq 0 (
    echo.
    echo [WARNING] Setup finished with warnings. Review the output above.
    pause
)
echo.
echo Setup completed. Launching OSINT Toolkit...
timeout /t 2 >nul
goto run_app

:run_app
python "%ROOT_DIR%app.py" %*
exit /b %errorlevel%
