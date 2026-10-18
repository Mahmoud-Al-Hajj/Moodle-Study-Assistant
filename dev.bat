@echo off
rem Start the web UI (API + app) for development. All dev.py flags are passed through.
"%~dp0.venv\Scripts\python.exe" "%~dp0dev.py" %*
exit /b %ERRORLEVEL%
