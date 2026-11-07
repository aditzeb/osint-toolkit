@echo off
title OSINT Toolkit - Master Control Center (8 Engines)
:menu
cls
echo ======================================================================
echo                         OSINT TOOLKIT (WINDOWS 11)
echo   Sherlock ^| Maigret ^| Osintgram ^| Numint ^| Snoop ^| Holehe ^| GHunt ^| ID
echo ======================================================================
echo.
echo  --- INDONESIA SPECIALIZED OSINT SUITE ---
echo  [1] Indonesia OSINT Suite - NIK KTP, NIP ASN, E-Wallet VA, Plat ^& PDDikti
echo.
echo  --- USERNAME ^& SOCIAL MEDIA OSINT ---
echo  [2] Sherlock       - Scan username across 400+ platforms (CLI)
echo  [3] Maigret        - Scan username dossier across 5,900+ sites (CLI)
echo  [4] Maigret Web    - Launch Maigret Web Graph UI (Port 5000)
echo.
echo  --- EMAIL ^& GOOGLE ACCOUNT INTELLIGENCE ---
echo  [5] Holehe         - Check Email registration across 120+ sites (CLI)
echo  [6] GHunt          - Google / Gmail Account Intelligence (Maps, Gaia, Drive)
echo.
echo  --- INSTAGRAM RECONNAISSANCE ---
echo  [7] Osintgram Web  - Launch Osintgram Web Dashboard (Port 8000)
echo  [8] Insta Login    - Authenticate Instagram (Username/Pass + 2FA)
echo  [9] Insta Session  - Authenticate Instagram (Browser Session ID)
echo.
echo  --- PHONE ^& PERSONA INTELLIGENCE ---
echo  [10] Numint        - Phone Number Intelligence Profile (CLI)
echo  [11] Numint Web    - Launch Numint Web Dashboard (Port 8080)
echo  [12] Snoop         - Person Footprint ^& Evidence Audit (CLI - SerpAPI Ready)
echo  [13] Snoop Web     - Launch Snoop Web Workspace (Port 8005)
echo.
echo  --- SYSTEM ^& TOOLS ---
echo  [14] OSINT Terminal - Command Prompt with all tool environments in PATH
echo  [0]  Exit
echo.
echo ======================================================================
set "CHOICE="
set /p CHOICE="Enter your choice [0-14]: "

if "%CHOICE%"=="1" goto opt_indo
if "%CHOICE%"=="2" goto opt_sherlock
if "%CHOICE%"=="3" goto opt_maigret
if "%CHOICE%"=="4" goto opt_maigret_web
if "%CHOICE%"=="5" goto opt_holehe
if "%CHOICE%"=="6" goto opt_ghunt
if "%CHOICE%"=="7" goto opt_osintgram
if "%CHOICE%"=="8" goto opt_insta_login
if "%CHOICE%"=="9" goto opt_insta_sid
if "%CHOICE%"=="10" goto opt_numint
if "%CHOICE%"=="11" goto opt_numint_web
if "%CHOICE%"=="12" goto opt_snoop
if "%CHOICE%"=="13" goto opt_snoop_web
if "%CHOICE%"=="14" goto opt_cmd
if "%CHOICE%"=="0" goto opt_exit

echo Invalid selection. Please try again.
timeout /t 2 >nul
goto menu

:opt_indo
cls
call "%~dp0indo_osint.bat"
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

:opt_holehe
cls
call "%~dp0holehe.bat"
goto menu

:opt_ghunt
cls
call "%~dp0ghunt.bat"
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
cmd /k "set PATH=%~dp0sherlock\.venv\Scripts;%~dp0maigret\.venv\Scripts;%~dp0Osintgram\.venv\Scripts;%~dp0numint\.venv\Scripts;%~dp0snoop\.venv\Scripts;%~dp0holehe\.venv\Scripts;%~dp0GHunt\.venv\Scripts;%PATH% & echo Ready: indo_osint.bat, sherlock, maigret, holehe, ghunt, uvicorn, numint, snoop"
goto menu

:opt_exit
exit /b 0
