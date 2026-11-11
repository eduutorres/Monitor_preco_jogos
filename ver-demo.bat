@echo off
cd /d "%~dp0"
title Painel de demonstracao
python codigo\gerar_demo.py
start "" cmd /c "timeout /t 2 >nul & start http://localhost:8787"
python codigo\api.py --demo
pause
