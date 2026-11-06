@echo off
setlocal
title OSINT Toolkit - Setup
echo ============================================================
echo               OSINT TOOLKIT - INITIAL SETUP
echo    Sherlock ^| Maigret ^| Osintgram ^| Numint ^| Snoop
echo ============================================================
echo.

:: 1. Check Python installation
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in your PATH.
    echo Please install Python 3.11+ from https://www.python.org/ or Microsoft Store.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo [INFO] Found %%i
echo.

set "ROOT_DIR=%~dp0"

:: 2. Setup Sherlock
echo [1/5] Setting up Sherlock (Username OSINT across 400+ platforms)...
if not exist "%ROOT_DIR%sherlock\.venv" (
    echo       Creating virtual environment...
    python -m venv "%ROOT_DIR%sherlock\.venv"
)
echo       Installing dependencies...
"%ROOT_DIR%sherlock\.venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>nul
"%ROOT_DIR%sherlock\.venv\Scripts\pip.exe" install -e "%ROOT_DIR%sherlock" >nul 2>nul
if %errorlevel% equ 0 (
    echo       [OK] Sherlock setup complete.
) else (
    echo       [WARNING] Sherlock setup encountered an issue. Check pip output.
)
echo.

:: 3. Setup Maigret
echo [2/5] Setting up Maigret (Dossier profiler across 5,900+ sites)...
if not exist "%ROOT_DIR%maigret\.venv" (
    echo       Creating virtual environment...
    python -m venv "%ROOT_DIR%maigret\.venv"
)
echo       Installing dependencies...
"%ROOT_DIR%maigret\.venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>nul
"%ROOT_DIR%maigret\.venv\Scripts\pip.exe" install -e "%ROOT_DIR%maigret" >nul 2>nul
if %errorlevel% equ 0 (
    echo       [OK] Maigret setup complete.
) else (
    echo       [WARNING] Maigret setup encountered an issue. Check pip output.
)
echo.

:: 4. Setup Osintgram
echo [3/5] Setting up Osintgram (Instagram Intelligence Dashboard)...
if not exist "%ROOT_DIR%Osintgram\.venv" (
    echo       Creating virtual environment...
    python -m venv "%ROOT_DIR%Osintgram\.venv"
)
echo       Installing dependencies...
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

:: 5. Setup Numint
echo [4/5] Setting up Numint (Phone Number Intelligence ^& Web UI)...
if not exist "%ROOT_DIR%numint\.venv" (
    echo       Creating virtual environment...
    python -m venv "%ROOT_DIR%numint\.venv"
)
echo       Installing dependencies...
"%ROOT_DIR%numint\.venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>nul
"%ROOT_DIR%numint\.venv\Scripts\pip.exe" install -e "%ROOT_DIR%numint[web,pdf]" >nul 2>nul
if %errorlevel% equ 0 (
    echo       [OK] Numint setup complete.
) else (
    echo       [WARNING] Numint setup encountered an issue. Check pip output.
)
echo.

:: 6. Setup Snoop
echo [5/5] Setting up Snoop (Persona Footprint ^& Evidence Investigation)...
if not exist "%ROOT_DIR%snoop\.venv" (
    echo       Creating virtual environment...
    python -m venv "%ROOT_DIR%snoop\.venv"
)
echo       Installing dependencies...
"%ROOT_DIR%snoop\.venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>nul
"%ROOT_DIR%snoop\.venv\Scripts\pip.exe" install -e "%ROOT_DIR%snoop[pdf]" >nul 2>nul
if %errorlevel% equ 0 (
    echo       [OK] Snoop setup complete.
) else (
    echo       [WARNING] Snoop setup encountered an issue. Check pip output.
)
echo.

echo ============================================================
echo                SETUP COMPLETED SUCCESSFULLY!
echo ============================================================
echo All 5 OSINT engines are configured and ready to use.
echo Launching the master menu now...
timeout /t 3 >nul
call "%ROOT_DIR%menu.bat"
