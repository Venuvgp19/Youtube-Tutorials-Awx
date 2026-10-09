@echo off
REM AWX Studio launcher: serves this folder on localhost (needed for screen capture + folder saving) and opens Chrome.
cd /d "%~dp0"
start "" http://localhost:8765/index.html
python -m http.server 8765
