@echo off
rem Double-click launcher. Installs on first run, then starts backend + frontend.
cd /d "%~dp0"
if not exist "backend\.venv" call npm install
npm start
