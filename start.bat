@echo off
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 launcher.py
) else (
  python launcher.py
)
if errorlevel 1 (
  echo Install Python 3.10+ from python.org and enable Add Python to PATH.
  pause
)
