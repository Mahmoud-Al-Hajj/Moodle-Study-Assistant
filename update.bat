@echo off
rem Run update.py with the project's virtual environment, from any folder.
rem   .\update               (PowerShell, in the project folder)
rem   .\update --no-open     (all update.py flags are passed through)
"%~dp0.venv\Scripts\python.exe" "%~dp0update.py" %*
exit /b %ERRORLEVEL%
