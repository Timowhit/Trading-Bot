@echo off
cd /d "%~dp0"
call .venv\Scripts\activate
start http://localhost:5000
python dashboard.py
python trader.py
python trader_with_dashboard.py