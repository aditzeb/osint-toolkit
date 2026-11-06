@echo off
setlocal
cd /d "%~dp0"

if not "%~1"=="" goto run_with_args

set "NAME_INPUT="
set /p NAME_INPUT="Enter target full name or handle: "
if "%NAME_INPUT%"=="" exit /b 0

.\.venv\Scripts\snoop.exe "%NAME_INPUT%"
pause
exit /b 0

:run_with_args
.\.venv\Scripts\snoop.exe %*
