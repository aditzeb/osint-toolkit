@echo off
setlocal
cd /d "%~dp0"
echo Starting Numint Web UI on http://127.0.0.1:8080 ...
start "" "http://127.0.0.1:8080"
.\.venv\Scripts\numint.exe web --port 8080
