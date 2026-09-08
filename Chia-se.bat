@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PY=C:\Users\Lenovo\Sumo\PPO_Train\Script\Scripts\python.exe
if not exist "%PY%" set PY=runtime\python\python.exe
if not exist "%PY%" set PY=python
"%PY%" chia_se.py
pause
