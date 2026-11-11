@echo off
cd /d "%~dp0"
title Monitor de precos de jogos
start "" cmd /c "timeout /t 4 >nul & start http://localhost:8787"
python codigo\monitor.py
pause
