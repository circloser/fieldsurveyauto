@echo off
REM ===== Field Survey DB - launcher (double-click) =====
REM Korean user guide is in the README file. Batch text is ASCII for reliability.
chcp 65001 >nul
cd /d "%~dp0"

REM First run: install if venv is missing
if not exist ".venv\Scripts\python.exe" (
  echo First run detected. Installing...
  call install.bat
  if errorlevel 1 exit /b 1
)

REM Start server (browser opens automatically)
".venv\Scripts\python.exe" run.py

pause
