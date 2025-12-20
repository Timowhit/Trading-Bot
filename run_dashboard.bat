@echo off
cd /d "%~dp0"
call .venv\Scripts\activate
start http://192.168.0.47:5000
python dashboard.py
python trader.py
python trader_with_dashboard.py