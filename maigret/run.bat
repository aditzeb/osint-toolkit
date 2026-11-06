@echo off
setlocal
cd /d "%~dp0"

if not "%~1"=="" goto run_with_args

set "TARGET_USER="
set /p TARGET_USER="Enter username to search (or --help / --web): "
if "%TARGET_USER%"=="" exit /b 0

.\.venv\Scripts\maigret.exe %TARGET_USER%
pause
exit /b 0

:run_with_args
.\.venv\Scripts\maigret.exe %*
