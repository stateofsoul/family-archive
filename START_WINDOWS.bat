@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto dependencies
where py >nul 2>nul
if errorlevel 1 goto use_python
py -m venv .venv
if errorlevel 1 goto failed
goto dependencies
:use_python
python -m venv .venv
if errorlevel 1 goto failed
:dependencies
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo.
echo Open http://127.0.0.1:5000 in your browser.
echo Keep this window open. Press Ctrl+C to stop.
".venv\Scripts\python.exe" app.py
if errorlevel 1 goto failed
goto end
:failed
echo.
echo Could not start. Check Python installation and internet connection.
echo See README.md for manual setup.
pause
:end
endlocal
