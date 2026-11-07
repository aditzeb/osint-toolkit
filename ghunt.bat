@echo off
setlocal
set SCRIPT_DIR=%~dp0
set GHUNT_EXE=%SCRIPT_DIR%GHunt\.venv\Scripts\ghunt.exe

if not exist "%GHUNT_EXE%" (
    echo [ERROR] GHunt virtual environment not found at:
    echo "%GHUNT_EXE%"
    pause
    exit /b 1
)

if not "%~1"=="" goto run_with_args

echo ============================================================
echo                  GHUNT GOOGLE ACCOUNT OSINT
echo ============================================================
echo  [1] Investigate Gmail Address  (ghunt email user@gmail.com)
echo  [2] Investigate Google Gaia ID (ghunt gaia ^<id^>)
echo  [3] Authenticate GHunt Session (ghunt login - required once)
echo  [4] Show GHunt Help
echo ============================================================
set "GH_CHOICE="
set /p GH_CHOICE="Select option [1-4]: "

if "%GH_CHOICE%"=="1" goto gh_email
if "%GH_CHOICE%"=="2" goto gh_gaia
if "%GH_CHOICE%"=="3" goto gh_login

"%GHUNT_EXE%" --help
pause
exit /b 0

:gh_email
set "TARGET_GMAIL="
set /p TARGET_GMAIL="Enter target @gmail.com address: "
if "%TARGET_GMAIL%"=="" exit /b 0
"%GHUNT_EXE%" email %TARGET_GMAIL%
pause
exit /b 0

:gh_gaia
set "TARGET_GAIA="
set /p TARGET_GAIA="Enter Google Gaia ID: "
if "%TARGET_GAIA%"=="" exit /b 0
"%GHUNT_EXE%" gaia %TARGET_GAIA%
pause
exit /b 0

:gh_login
"%GHUNT_EXE%" login
pause
exit /b 0

:run_with_args
"%GHUNT_EXE%" %*
