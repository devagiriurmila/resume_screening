@echo off
REM One-time setup for Windows. Double-click or run from a terminal in the project folder.
cd /d "%~dp0.."
echo === Intelligent Resume Screening - setup ===

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python was not found. Install Python 3.10-3.12 from https://www.python.org/downloads/
  echo         and tick "Add python.exe to PATH" during installation. Then run this file again.
  pause
  exit /b 1
)

if not exist venv (
  echo Creating virtual environment...
  python -m venv venv
  if errorlevel 1 ( echo [ERROR] Could not create the virtual environment. & pause & exit /b 1 )
)
call venv\Scripts\activate.bat

echo Installing packages...
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 ( echo [ERROR] Package installation failed. See README troubleshooting. & pause & exit /b 1 )

if not exist .env (
  copy .env.example .env >nul
  echo Created .env from .env.example - edit it if Tesseract is installed somewhere else.
)

if not exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
  where tesseract >nul 2>nul
  if errorlevel 1 (
    echo [WARNING] Tesseract OCR was not found. Text PDFs will work, but scanned PDFs will be flagged.
    echo           Install it from https://github.com/UB-Mannheim/tesseract/wiki and set TESSERACT_CMD in .env
  )
)

echo Initialising database and sample job...
python database\seed.py
echo Generating fictional sample resumes...
python sample_data\GenerateSampleResumes.py

echo.
echo Setup complete. Start the app with scripts\run_app.bat
pause
