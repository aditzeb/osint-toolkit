@echo off
setlocal
cd /d "%~dp0"
echo Starting Osintgram web interface on http://127.0.0.1:8000 ...
start "" "http://127.0.0.1:8000"
.\.venv\Scripts\uvicorn.exe src.web.app:app --host 127.0.0.1 --port 8000 --reload

