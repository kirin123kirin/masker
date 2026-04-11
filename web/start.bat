@echo off
cd /d %~dp0
start http://localhost:8765
python -m http.server 8765
pause
