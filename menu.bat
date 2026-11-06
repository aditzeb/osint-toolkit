@echo off
title OSINT Toolkit - Master Menu
:menu
cls
echo ============================================================
echo                      OSINT TOOLKIT
echo     Sherlock ^| Maigret ^| Osintgram ^| Numint ^| Snoop
echo ============================================================
echo.
echo  --- USERNAME ^& SOCIAL OSINT ---
echo  [1] Sherlock       - Scan username across 400+ platforms (CLI)
echo  [2] Maigret        - Scan username dossier across 5,900+ sites (CLI)
echo  [3] Maigret Web    - Launch Maigret Web Graph UI (Port 5000)
echo.
echo  --- INSTAGRAM RECONNAISSANCE ---
echo  [4] Osintgram Web  - Launch Osintgram Web Dashboard (Port 8000)
echo  [5] Insta Login    - Authenticate Instagram (Username/Pass + 2FA)
echo  [6] Insta Session  - Authenticate Instagram (Browser Session ID)
echo.
echo  --- PHONE ^& PERSONA INTELLIGENCE ---
echo  [7] Numint         - Phone Number Intelligence Profile (CLI)
echo  [8] Numint Web     - Launch Numint Web Dashboard (Port 8080)
echo  [9] Snoop          - Person Footprint ^& Evidence Audit (CLI)
echo  [10] Snoop Web     - Launch Snoop Web Workspace (Port 8005)
echo.
echo  --- SYSTEM ^& TOOLS ---
echo  [11] OSINT Terminal - Command Prompt with all 5 tool environments
echo  [0]  Exit
echo.
echo ============================================================
set /p CHOICE="Enter your choice [0-11]: "

if "%CHOICE%"=="1" goto opt_sherlock
if "%CHOICE%"=="2" goto opt_maigret
if "%CHOICE%"=="3" goto opt_maigret_web
if "%CHOICE%"=="4" goto opt_osintgram
if "%CHOICE%"=="5" goto opt_insta_login
if "%CHOICE%"=="6" goto opt_insta_sid
if "%CHOICE%"=="7" goto opt_numint
if "%CHOICE%"=="8" goto opt_numint_web
if "%CHOICE%"=="9" goto opt_snoop
if "%CHOICE%"=="10" goto opt_snoop_web
if "%CHOICE%"=="11" goto opt_cmd
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
echo Starting Maigret Web UI on http://127.0.0.1:5000 ...
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

:opt_numint
cls
call "%~dp0numint.bat"
goto menu

:opt_numint_web
cls
call "%~dp0numint_web.bat"
goto menu

:opt_snoop
cls
call "%~dp0snoop.bat"
goto menu

:opt_snoop_web
cls
call "%~dp0snoop_web.bat"
goto menu

:opt_cmd
cls
echo Starting Command Prompt with all OSINT tool environments...
cmd /k "set PATH=%~dp0sherlock\.venv\Scripts;%~dp0maigret\.venv\Scripts;%~dp0Osintgram\.venv\Scripts;%~dp0numint\.venv\Scripts;%~dp0snoop\.venv\Scripts;%PATH% & echo Ready: sherlock, maigret, uvicorn, numint, snoop"
goto menu

:opt_exit
exit /b 0
