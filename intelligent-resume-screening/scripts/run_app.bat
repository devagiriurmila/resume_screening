@echo off
REM Starts the Flask web application and opens the browser.
cd /d "%~dp0.."
if not exist venv\Scripts\activate.bat (
  echo [ERROR] Virtual environment missing. Run scripts\setup_windows.bat first.
  pause
  exit /b 1
)
call venv\Scripts\activate.bat
start "" cmd /c "timeout /t 3 >nul & start http://127.0.0.1:5000"
python app.py
pause
