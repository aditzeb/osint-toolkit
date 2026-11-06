@echo off
title OSINT Toolkit - Master Menu
:menu
cls
echo ============================================================
echo                      OSINT TOOLKIT
echo             Sherlock ^| Maigret ^| Osintgram
echo ============================================================
echo.
echo  [1] Sherlock  - Scan username across 400+ platforms (CLI)
echo  [2] Maigret   - Scan username across 5,900+ sites (CLI)
echo  [3] Maigret Web UI  - Launch Maigret Web Interface
echo  [4] Osintgram Web UI - Launch Osintgram Web Interface
echo.
echo  -- Osintgram Instagram Authentication (instagrapi) --
echo  [5] Login Instagram with Username/Password (+ 2FA)
echo  [6] Login Instagram with Browser Session ID (Recommended)
echo.
echo  [7] Open OSINT Command Prompt (Environment Ready)
echo  [0] Exit
echo.
echo ============================================================
set /p CHOICE="Enter your choice [0-7]: "

if "%CHOICE%"=="1" goto opt_sherlock
if "%CHOICE%"=="2" goto opt_maigret
if "%CHOICE%"=="3" goto opt_maigret_web
if "%CHOICE%"=="4" goto opt_osintgram
if "%CHOICE%"=="5" goto opt_insta_login
if "%CHOICE%"=="6" goto opt_insta_sid
if "%CHOICE%"=="7" goto opt_cmd
if "%CHOICE%"=="0" goto opt_exit

echo Invalid selection. Please try again.
timeout /t 2 >nul
goto menu

:opt_sherlock
cls
call "%~dp0sherlock.bat"
goto menu

:opt_maigret
cls
call "%~dp0maigret.bat"
goto menu

:opt_maigret_web
cls
echo ============================================================
echo Starting Maigret Web UI on http://127.0.0.1:5000 ...
echo ============================================================
start "" "http://127.0.0.1:5000"
"%~dp0maigret\.venv\Scripts\maigret.exe" --web 5000
goto menu

:opt_osintgram
cls
call "%~dp0osintgram.bat"
goto menu

:opt_insta_login
cls
call "%~dp0Osintgram\login_instagram.bat"
goto menu

:opt_insta_sid
cls
call "%~dp0Osintgram\login_session_id.bat"
goto menu

:opt_cmd
cls
echo Starting Command Prompt with all OSINT tool environments...
cmd /k "set PATH=%~dp0sherlock\.venv\Scripts;%~dp0maigret\.venv\Scripts;%~dp0Osintgram\.venv\Scripts;%PATH% & echo Type sherlock, maigret, or uvicorn to run."
goto menu

:opt_exit
exit /b 0
