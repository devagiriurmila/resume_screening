@echo off
REM Example of the command UiPath runs. Edit the folders / job id as needed. The web app must be running
REM (or add --start-server).
cd /d "%~dp0.."
call venv\Scripts\activate.bat
python scripts\process_resumes.py --input-folder sample_data\resumes --output-folder outputs --job-id 1 --start-server
echo Exit code: %ERRORLEVEL%
pause
