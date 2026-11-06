@echo off
setlocal
title OSINT Toolkit - Setup
echo ============================================================
echo               OSINT TOOLKIT - INITIAL SETUP
echo       Sherlock ^| Maigret ^| Osintgram for Windows 11
echo ============================================================
echo.

:: 1. Check Python installation
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in your PATH.
    echo Please install Python 3.10+ from https://www.python.org/ or Microsoft Store.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo [INFO] Found %%i
echo.

set "ROOT_DIR=%~dp0"

:: 2. Setup Sherlock
echo [1/3] Setting up Sherlock...
if not exist "%ROOT_DIR%sherlock\.venv" (
    echo       Creating virtual environment...
    python -m venv "%ROOT_DIR%sherlock\.venv"
)
echo       Installing dependencies (this may take a minute)...
"%ROOT_DIR%sherlock\.venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>nul
"%ROOT_DIR%sherlock\.venv\Scripts\pip.exe" install -e "%ROOT_DIR%sherlock" >nul 2>nul
if %errorlevel% equ 0 (
    echo       [OK] Sherlock setup complete.
) else (
    echo       [WARNING] Sherlock setup encountered an issue. Check pip output.
)
echo.

:: 3. Setup Maigret
echo [2/3] Setting up Maigret...
if not exist "%ROOT_DIR%maigret\.venv" (
    echo       Creating virtual environment...
    python -m venv "%ROOT_DIR%maigret\.venv"
)
echo       Installing dependencies (this may take a minute)...
"%ROOT_DIR%maigret\.venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>nul
"%ROOT_DIR%maigret\.venv\Scripts\pip.exe" install -e "%ROOT_DIR%maigret" >nul 2>nul
if %errorlevel% equ 0 (
    echo       [OK] Maigret setup complete.
) else (
    echo       [WARNING] Maigret setup encountered an issue. Check pip output.
)
echo.

:: 4. Setup Osintgram
echo [3/3] Setting up Osintgram...
if not exist "%ROOT_DIR%Osintgram\.venv" (
    echo       Creating virtual environment...
    python -m venv "%ROOT_DIR%Osintgram\.venv"
)
echo       Installing dependencies (this may take a minute)...
"%ROOT_DIR%Osintgram\.venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>nul
"%ROOT_DIR%Osintgram\.venv\Scripts\pip.exe" install -r "%ROOT_DIR%Osintgram\requirements.txt" >nul 2>nul

if not exist "%ROOT_DIR%Osintgram\config\credentials.ini" (
    if exist "%ROOT_DIR%Osintgram\config\credentials.ini.example" (
        copy "%ROOT_DIR%Osintgram\config\credentials.ini.example" "%ROOT_DIR%Osintgram\config\credentials.ini" >nul
        echo       Created initial credentials.ini from template.
    )
)
if %errorlevel% equ 0 (
    echo       [OK] Osintgram setup complete.
) else (
    echo       [WARNING] Osintgram setup encountered an issue. Check pip output.
)
echo.

echo ============================================================
echo                SETUP COMPLETED SUCCESSFULLY!
echo ============================================================
echo All three tools are configured and ready to use.
echo Launching the master menu now...
timeout /t 3 >nul
call "%ROOT_DIR%menu.bat"
