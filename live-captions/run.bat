@echo off
cd /d "%~dp0"
setlocal
if exist .venv\Scripts\python.exe goto run
echo Creating a local Python environment and installing dependencies...
where py >nul 2>&1
if %errorlevel%==0 (
  py -3 -m venv .venv
) else (
  python -m venv .venv
)
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto fail
:run
.venv\Scripts\python.exe -m live_captions %*
if errorlevel 1 goto fail
exit /b 0
:fail
echo.
echo Optic live captions could not start. Read the message above.
pause
exit /b 1
