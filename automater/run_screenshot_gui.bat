@echo off
title Screenshot Automater GUI
cd /d "%~dp0"
python screenshot_automater_gui.py %*
if errorlevel 1 pause
