@echo off
setlocal
cd /d "%~dp0"
echo Starting Snoop Web Workspace on http://127.0.0.1:8005 ...
start "" "http://127.0.0.1:8005"
.\.venv\Scripts\snoop.exe web --port 8005
