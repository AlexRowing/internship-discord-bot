@echo off
REM Bulletproof launcher: always uses this folder's venv Python, correct working dir.
cd /d "%~dp0"
".venv\Scripts\python.exe" run.py
pause
