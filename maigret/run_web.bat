@echo off
setlocal
cd /d "%~dp0"
echo Starting Maigret Web UI on http://127.0.0.1:5000 ...
start "" "http://127.0.0.1:5000"
.\.venv\Scripts\maigret.exe --web 5000

