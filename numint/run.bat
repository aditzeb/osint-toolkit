@echo off
setlocal
cd /d "%~dp0"

if not "%~1"=="" goto run_with_args

set "PHONE_INPUT="
set /p PHONE_INPUT="Enter phone number to scan (e.g. +14155550123): "
if "%PHONE_INPUT%"=="" exit /b 0

.\.venv\Scripts\numint.exe scan %PHONE_INPUT%
pause
exit /b 0

:run_with_args
.\.venv\Scripts\numint.exe %*
