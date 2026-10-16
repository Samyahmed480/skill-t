@echo off
title Antigravity Telegram Dashboard Launcher
chcp 65001 > nul
cd /d "%~dp0"

echo ===================================================
echo   Antigravity x Telegram Bridge Dashboard
echo ===================================================
echo [1/2] Launching browser at http://localhost:8765 ...
start http://localhost:8765

echo [2/2] Starting Dashboard Server on port 8765 ...
python server.py
pause
