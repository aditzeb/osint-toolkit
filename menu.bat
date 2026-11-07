@echo off
setlocal enabledelayedexpansion
title OSINT Toolkit - All-in-One Master Navigator (8 Engines)

:: Check if user explicitly wants pure batch mode
if "%~1"=="--batch" goto batch_main_menu
if "%~1"=="-b" goto batch_main_menu

:: Check if Python is installed to launch the rich interactive Python Navigator
where python >nul 2>nul
if %errorlevel% equ 0 (
    if exist "%~dp0app.py" (
        python "%~dp0app.py" %*
        exit /b %errorlevel%
    )
)

:batch_main_menu
cls
echo ======================================================================
echo             OSINT TOOLKIT - ALL-IN-ONE BATCH NAVIGATOR
echo   Sherlock ^| Maigret ^| Osintgram ^| Numint ^| Snoop ^| Holehe ^| GHunt ^| ID
echo ======================================================================
echo.
echo  [1] Target Investigation   - Guided workflow by Username, Email, Phone, NIK
echo  [2] Individual Engines     - Dedicated CLI workspaces with custom options
echo  [3] Web Dashboards Hub     - Launch Web UIs (Ports 5000, 8000, 8080, 8005)
echo  [4] Reports ^& Evidence     - Open centralized reports folder in Explorer
echo  [5] System Diagnostics     - Verify virtual environments ^& run setup.bat
echo  [6] OSINT Terminal Shell   - Spawns Command Prompt with all 8 venvs in PATH
echo  [0] Exit
echo.
echo ======================================================================
set "MAIN_CHOICE="
set /p MAIN_CHOICE="Select category [0-6]: "

if "%MAIN_CHOICE%"=="1" goto batch_target_menu
if "%MAIN_CHOICE%"=="2" goto batch_engines_menu
if "%MAIN_CHOICE%"=="3" goto batch_web_menu
if "%MAIN_CHOICE%"=="4" goto batch_reports
if "%MAIN_CHOICE%"=="5" goto batch_diagnostics
if "%MAIN_CHOICE%"=="6" goto batch_terminal
if "%MAIN_CHOICE%"=="0" exit /b 0

echo Invalid choice. Please try again.
timeout /t 1 >nul
goto batch_main_menu


:: ======================================================================
:: 1. TARGET INVESTIGATION SUBMENU
:: ======================================================================
:batch_target_menu
cls
echo ======================================================================
echo             TARGET INVESTIGATION WORKFLOWS (ALL-IN-ONE)
echo ======================================================================
echo.
echo  [1] 👤 Username Investigation   - Sherlock (400+) ^& Maigret (5,900+)
echo  [2] 📧 Email Intelligence       - Holehe (120+) ^& GHunt (Google/Gaia)
echo  [3] 📱 Phone Number Intel       - Numint Carrier/Risk ^& Indo E-Wallet VA
echo  [4] 🇮🇩 Indonesia Regional Suite - NIK KTP, NIP ASN, Plat Nomor ^& Dorks
echo  [5] 📸 Instagram Recon          - Osintgram Web UI ^& Session Login
echo  [6] 🕵️ Persona Footprint Audit  - Snoop Evidence-Backed Case Search
echo.
echo  [B] Back to Main Menu
echo  [0] Exit
echo ======================================================================
set "T_CHOICE="
set /p T_CHOICE="Select target type [1-6, B, 0]: "

if /i "%T_CHOICE%"=="b" goto batch_main_menu
if "%T_CHOICE%"=="0" exit /b 0

if "%T_CHOICE%"=="1" goto batch_target_username
if "%T_CHOICE%"=="2" goto batch_target_email
if "%T_CHOICE%"=="3" goto batch_target_phone
if "%T_CHOICE%"=="4" goto batch_target_indo
if "%T_CHOICE%"=="5" goto batch_target_insta
if "%T_CHOICE%"=="6" goto batch_target_snoop

echo Invalid choice.
timeout /t 1 >nul
goto batch_target_menu

:batch_target_username
cls
echo ============================================================
echo               USERNAME INVESTIGATION RECON
echo ============================================================
echo.
set "U_TARGET="
set /p U_TARGET="Enter target username: "
if "%U_TARGET%"=="" goto batch_target_menu

echo.
echo Select scan mode for '%U_TARGET%':
echo  [1] Fast Scan        - Sherlock (400+ social platforms)
echo  [2] Deep Dossier     - Maigret (top 500 sites with PDF/HTML)
echo  [3] Exhaustive Scan  - Maigret (all 5,900+ sites)
echo  [4] Dual-Engine Scan - Runs Sherlock, then Maigret
echo  [B] Back
set "U_MODE="
set /p U_MODE="Select mode [1-4, B]: "

if /i "%U_MODE%"=="b" goto batch_target_menu
cls
if "%U_MODE%"=="1" (
    call "%~dp0sherlock.bat" %U_TARGET%
) else if "%U_MODE%"=="2" (
    call "%~dp0maigret.bat" %U_TARGET%
) else if "%U_MODE%"=="3" (
    call "%~dp0maigret.bat" %U_TARGET% -a
) else if "%U_MODE%"=="4" (
    echo [*] STAGE 1/2: Sherlock Scan...
    call "%~dp0sherlock.bat" %U_TARGET%
    echo.
    echo [*] STAGE 2/2: Maigret Dossier Scan...
    call "%~dp0maigret.bat" %U_TARGET%
)
pause
goto batch_target_menu

:batch_target_email
cls
echo ============================================================
echo                 EMAIL INTELLIGENCE RECON
echo ============================================================
echo.
set "E_TARGET="
set /p E_TARGET="Enter target email address: "
if "%E_TARGET%"=="" goto batch_target_menu

echo.
echo Select mode for '%E_TARGET%':
echo  [1] Holehe (Check registration across 120+ platforms)
echo  [2] Holehe Used Only (Show registered sites only)
echo  [3] GHunt (Google Account, Gaia ID, Maps reviews, Drive)
echo  [4] Dual Email Scan (Run Holehe + GHunt)
echo  [B] Back
set "E_MODE="
set /p E_MODE="Select mode [1-4, B]: "

if /i "%E_MODE%"=="b" goto batch_target_menu
cls
if "%E_MODE%"=="1" (
    call "%~dp0holehe.bat" %E_TARGET%
) else if "%E_MODE%"=="2" (
    call "%~dp0holehe.bat" --only-used %E_TARGET%
) else if "%E_MODE%"=="3" (
    call "%~dp0ghunt.bat" email %E_TARGET%
) else if "%E_MODE%"=="4" (
    echo [*] STAGE 1/2: Holehe Scan...
    call "%~dp0holehe.bat" --only-used %E_TARGET%
    echo.
    echo [*] STAGE 2/2: GHunt Scan...
    call "%~dp0ghunt.bat" email %E_TARGET%
)
pause
goto batch_target_menu

:batch_target_phone
cls
echo ============================================================
echo                PHONE NUMBER INTELLIGENCE
echo ============================================================
echo.
set "P_TARGET="
set /p P_TARGET="Enter phone number (e.g. +628123456789 or 08123456789): "
if "%P_TARGET%"=="" goto batch_target_menu

echo.
echo Select phone intelligence module:
echo  [1] Global Phone Intelligence (Numint - carrier, line type, risk score)
echo  [2] Indonesian Telco & E-Wallet VA (Indo OSINT - DANA/OVO/GoPay/Shopee)
echo  [3] Combined Phone Recon (Numint + Indo OSINT Phone Analyzer)
echo  [B] Back
set "P_MODE="
set /p P_MODE="Select module [1-3, B]: "

if /i "%P_MODE%"=="b" goto batch_target_menu
cls
if "%P_MODE%"=="1" (
    call "%~dp0numint.bat" %P_TARGET%
) else if "%P_MODE%"=="2" (
    call "%~dp0indo_osint.bat" --phone %P_TARGET%
) else if "%P_MODE%"=="3" (
    echo [*] STAGE 1/2: Numint Global Scan...
    call "%~dp0numint.bat" %P_TARGET%
    echo.
    echo [*] STAGE 2/2: Indonesian Telco & E-Wallet VA Analysis...
    call "%~dp0indo_osint.bat" --phone %P_TARGET%
)
pause
goto batch_target_menu

:batch_target_indo
cls
echo ============================================================
echo            INDONESIA SPECIALIZED OSINT SUITE
echo ============================================================
echo.
echo  [1] 16-Digit NIK KTP Decoder
echo  [2] 18-Digit NIP ASN / PNS Decoder
echo  [3] Indonesian Phone & E-Wallet VA Generator
echo  [4] Plat Nomor TNKB Decoder
echo  [5] Indonesian Registry Dorks (PDDikti, Mahkamah Agung, LPSE)
echo  [6] Full Interactive Indo OSINT Menu
echo  [B] Back
set "ID_OPT="
set /p ID_OPT="Select option [1-6, B]: "

if /i "%ID_OPT%"=="b" goto batch_target_menu
cls
if "%ID_OPT%"=="1" (
    set "NIK_IN="
    set /p NIK_IN="Enter 16-digit NIK KTP: "
    if not "!NIK_IN!"=="" call "%~dp0indo_osint.bat" --nik !NIK_IN!
) else if "%ID_OPT%"=="2" (
    set "NIP_IN="
    set /p NIP_IN="Enter 18-digit NIP ASN: "
    if not "!NIP_IN!"=="" call "%~dp0indo_osint.bat" --nip !NIP_IN!
) else if "%ID_OPT%"=="3" (
    set "PH_IN="
    set /p PH_IN="Enter Indonesian Phone Number: "
    if not "!PH_IN!"=="" call "%~dp0indo_osint.bat" --phone !PH_IN!
) else if "%ID_OPT%"=="4" (
    set "PL_IN="
    set /p PL_IN="Enter Plat Nomor (e.g. B 1234 KAA): "
    if not "!PL_IN!"=="" call "%~dp0indo_osint.bat" --plate "!PL_IN!"
) else if "%ID_OPT%"=="5" (
    set "DK_IN="
    set /p DK_IN="Enter Name or Institution to Dork: "
    if not "!DK_IN!"=="" call "%~dp0indo_osint.bat" --dorks "!DK_IN!" --open
) else if "%ID_OPT%"=="6" (
    call "%~dp0indo_osint.bat"
)
pause
goto batch_target_menu

:batch_target_insta
cls
echo ============================================================
echo               INSTAGRAM RECONNAISSANCE
echo ============================================================
echo.
echo  [1] Launch Osintgram Web Dashboard (Port 8000)
echo  [2] Authenticate via Session ID (Cookie - Fast & Safe)
echo  [3] Authenticate via Username & Password (+ 2FA)
echo  [B] Back
set "IN_OPT="
set /p IN_OPT="Select option [1-3, B]: "

if /i "%IN_OPT%"=="b" goto batch_target_menu
cls
if "%IN_OPT%"=="1" (
    call "%~dp0osintgram.bat"
) else if "%IN_OPT%"=="2" (
    call "%~dp0login_instagram_sessionid.bat"
) else if "%IN_OPT%"=="3" (
    call "%~dp0login_instagram.bat"
)
pause
goto batch_target_menu

:batch_target_snoop
cls
echo ============================================================
echo            SNOOP PERSONA FOOTPRINT AUDIT
echo ============================================================
echo.
set "SN_TARGET="
set /p SN_TARGET="Enter target full name or alias: "
if "%SN_TARGET%"=="" goto batch_target_menu

echo.
echo  [1] Standard Persona Audit
echo  [2] Deep Persona Audit (--mode deep)
echo  [3] Launch Snoop Web Workspace (Port 8005)
echo  [B] Back
set "SN_OPT="
set /p SN_OPT="Select option [1-3, B]: "

if /i "%SN_OPT%"=="b" goto batch_target_menu
cls
if "%SN_OPT%"=="1" (
    call "%~dp0snoop.bat" "%SN_TARGET%"
) else if "%SN_OPT%"=="2" (
    call "%~dp0snoop.bat" "%SN_TARGET%" --mode deep
) else if "%SN_OPT%"=="3" (
    call "%~dp0snoop_web.bat"
)
pause
goto batch_target_menu


:: ======================================================================
:: 2. INDIVIDUAL ENGINES SUBMENU
:: ======================================================================
:batch_engines_menu
cls
echo ======================================================================
echo                INDIVIDUAL ENGINE WORKSPACES
echo ======================================================================
echo.
echo  [1] Sherlock CLI     - 400+ social platforms username hunter
echo  [2] Maigret CLI      - 5,900+ sites deep dossier profiler
echo  [3] Holehe CLI       - 120+ sites email registration checker
echo  [4] GHunt CLI        - Google / Gmail account intelligence
echo  [5] Numint CLI       - Phone number intelligence & carrier analysis
echo  [6] Snoop CLI        - Persona footprint audit & evidence linking
echo  [7] Indo OSINT Suite - Indonesian NIK, NIP, Phone, Plate & Dorks
echo  [8] Osintgram Web    - Instagram intelligence dashboard
echo.
echo  [B] Back to Main Menu
echo  [0] Exit
echo ======================================================================
set "ENG_CHOICE="
set /p ENG_CHOICE="Select engine [1-8, B, 0]: "

if /i "%ENG_CHOICE%"=="b" goto batch_main_menu
if "%ENG_CHOICE%"=="0" exit /b 0

cls
if "%ENG_CHOICE%"=="1" call "%~dp0sherlock.bat"
if "%ENG_CHOICE%"=="2" call "%~dp0maigret.bat"
if "%ENG_CHOICE%"=="3" call "%~dp0holehe.bat"
if "%ENG_CHOICE%"=="4" call "%~dp0ghunt.bat"
if "%ENG_CHOICE%"=="5" call "%~dp0numint.bat"
if "%ENG_CHOICE%"=="6" call "%~dp0snoop.bat"
if "%ENG_CHOICE%"=="7" call "%~dp0indo_osint.bat"
if "%ENG_CHOICE%"=="8" call "%~dp0osintgram.bat"
goto batch_engines_menu


:: ======================================================================
:: 3. WEB DASHBOARDS HUB SUBMENU
:: ======================================================================
:batch_web_menu
cls
echo ======================================================================
echo                     WEB DASHBOARDS HUB
echo ======================================================================
echo.
echo  [1] Launch Maigret Web UI   - http://127.0.0.1:5000 (Graph Visualizer)
echo  [2] Launch Osintgram Web UI  - http://127.0.0.1:8000 (FastAPI Dashboard)
echo  [3] Launch Numint Web UI     - http://127.0.0.1:8080 (Phone Dashboard)
echo  [4] Launch Snoop Web UI      - http://127.0.0.1:8005 (Case Workspace)
echo.
echo  [B] Back to Main Menu
echo  [0] Exit
echo ======================================================================
set "W_CHOICE="
set /p W_CHOICE="Select web dashboard [1-4, B, 0]: "

if /i "%W_CHOICE%"=="b" goto batch_main_menu
if "%W_CHOICE%"=="0" exit /b 0

if "%W_CHOICE%"=="1" (
    echo Starting Maigret Web UI on http://127.0.0.1:5000 ...
    start "" "http://127.0.0.1:5000"
    start "Maigret Web" "%~dp0maigret\.venv\Scripts\maigret.exe" --web 5000
) else if "%W_CHOICE%"=="2" (
    echo Starting Osintgram Web UI on http://127.0.0.1:8000 ...
    start "" "%~dp0osintgram.bat"
) else if "%W_CHOICE%"=="3" (
    echo Starting Numint Web UI on http://127.0.0.1:8080 ...
    start "" "%~dp0numint_web.bat"
) else if "%W_CHOICE%"=="4" (
    echo Starting Snoop Web UI on http://127.0.0.1:8005 ...
    start "" "%~dp0snoop_web.bat"
)
pause
goto batch_web_menu


:: ======================================================================
:: 4. REPORTS VIEWER
:: ======================================================================
:batch_reports
cls
echo Opening centralized reports folder in Windows Explorer...
if not exist "%~dp0reports" mkdir "%~dp0reports"
start explorer "%~dp0reports"
goto batch_main_menu


:: ======================================================================
:: 5. SYSTEM DIAGNOSTICS & SETUP
:: ======================================================================
:batch_diagnostics
cls
echo ======================================================================
echo                 SYSTEM DIAGNOSTICS & SETUP
echo ======================================================================
echo.
echo Checking virtual environments:
if exist "%~dp0sherlock\.venv\Scripts\sherlock.exe" ( echo  [OK] Sherlock  : .venv ready ) else ( echo  [MISSING] Sherlock  : Run setup.bat )
if exist "%~dp0maigret\.venv\Scripts\maigret.exe"   ( echo  [OK] Maigret   : .venv ready ) else ( echo  [MISSING] Maigret   : Run setup.bat )
if exist "%~dp0holehe\.venv\Scripts\holehe.exe"     ( echo  [OK] Holehe    : .venv ready ) else ( echo  [MISSING] Holehe    : Run setup.bat )
if exist "%~dp0GHunt\.venv\Scripts\ghunt.exe"       ( echo  [OK] GHunt     : .venv ready ) else ( echo  [MISSING] GHunt     : Run setup.bat )
if exist "%~dp0numint\.venv\Scripts\numint.exe"     ( echo  [OK] Numint    : .venv ready ) else ( echo  [MISSING] Numint    : Run setup.bat )
if exist "%~dp0snoop\.venv\Scripts\snoop.exe"       ( echo  [OK] Snoop     : .venv ready ) else ( echo  [MISSING] Snoop     : Run setup.bat )
if exist "%~dp0Osintgram\.venv\Scripts\uvicorn.exe" ( echo  [OK] Osintgram : .venv ready ) else ( echo  [MISSING] Osintgram : Run setup.bat )
if exist "%~dp0indo_osint\cli.py"                   ( echo  [OK] IndoOSINT : Stdlib ready ) else ( echo  [MISSING] IndoOSINT : Missing cli.py )
echo.
echo  [1] Run Full Automated Setup (setup.bat)
echo  [B] Back to Main Menu
set "DIAG_OPT="
set /p DIAG_OPT="Select option [1, B]: "

if "%DIAG_OPT%"=="1" (
    cls
    call "%~dp0setup.bat"
)
goto batch_main_menu


:: ======================================================================
:: 6. OSINT TERMINAL SHELL
:: ======================================================================
:batch_terminal
cls
echo ======================================================================
echo              SPAWNING OSINT DEVELOPER TERMINAL
echo ======================================================================
echo All 8 engine virtual environment paths are injected into PATH.
echo You can run 'sherlock', 'maigret', 'holehe', 'ghunt', 'numint', 'snoop' directly!
echo.
cmd /k "set PATH=%~dp0sherlock\.venv\Scripts;%~dp0maigret\.venv\Scripts;%~dp0Osintgram\.venv\Scripts;%~dp0numint\.venv\Scripts;%~dp0snoop\.venv\Scripts;%~dp0holehe\.venv\Scripts;%~dp0GHunt\.venv\Scripts;%PATH% & title OSINT Terminal Shell"
goto batch_main_menu
