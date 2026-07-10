@echo off
REM ===== Field Survey DB - first-time setup =====
REM Korean user guide is in the README file. Batch text is ASCII for reliability.
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   Field Survey DB - Setup
echo ============================================
echo.

REM Prefer Python 3.11, then any py, then python
set "PYEXE="
py -3.11 --version >nul 2>&1 && set "PYEXE=py -3.11"
if not defined PYEXE ( py --version >nul 2>&1 && set "PYEXE=py" )
if not defined PYEXE ( python --version >nul 2>&1 && set "PYEXE=python" )

if not defined PYEXE (
  echo [ERROR] Python not found.
  echo   Install Python 3.11 from https://www.python.org/downloads/
  echo   and CHECK "Add Python to PATH" during install, then run install.bat again.
  pause
  exit /b 1
)

echo Using Python: %PYEXE%
echo Creating virtual environment (.venv)...
%PYEXE% -m venv .venv
if errorlevel 1 ( echo [ERROR] venv creation failed & pause & exit /b 1 )

echo Installing libraries... (needs internet, may take a few minutes)
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 ( echo [ERROR] library install failed & pause & exit /b 1 )

echo.
echo [OK] Setup complete. Now double-click start.bat to run.
pause
