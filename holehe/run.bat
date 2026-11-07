@echo off
setlocal
cd /d "%~dp0"

if not "%~1"=="" goto run_with_args

set "EMAIL_INPUT="
set /p EMAIL_INPUT="Enter target email address: "
if "%EMAIL_INPUT%"=="" exit /b 0

.\.venv\Scripts\holehe.exe --only-used %EMAIL_INPUT%
pause
exit /b 0

:run_with_args
.\.venv\Scripts\holehe.exe %*
