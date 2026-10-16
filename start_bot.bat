@echo off
title Antigravity Telegram Bot Daemon
chcp 65001 > nul
cd /d "%~dp0"

echo ===================================================
echo   Starting Antigravity Telegram Bot Daemon ...
echo ===================================================
python scripts\bot_daemon.py
pause
