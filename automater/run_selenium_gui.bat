@echo off
echo Starting Selenium Screenshot Automater GUI...
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python selenium_automater_gui.py
pause
