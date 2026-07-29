@echo off
setlocal
cd /d "%~dp0"

set "VENV_PYTHON=.venv-windows\Scripts\python.exe"

if exist "%VENV_PYTHON%" goto launch

echo.
echo CubeZero Windows setup
echo ----------------------
echo Creating a Windows Python environment. This happens only once.
echo.

where py >nul 2>nul
if not errorlevel 1 (
    py -3 -m venv .venv-windows
) else (
    where python >nul 2>nul
    if errorlevel 1 goto python_missing
    python -m venv .venv-windows
)

if errorlevel 1 goto setup_failed

"%VENV_PYTHON%" -m pip install --upgrade pip
if errorlevel 1 goto setup_failed

"%VENV_PYTHON%" -m pip install -r requirements.txt
if errorlevel 1 goto setup_failed

:launch
"%VENV_PYTHON%" app.py
set "APP_EXIT=%ERRORLEVEL%"
if "%APP_EXIT%"=="0" exit /b 0

echo.
echo CubeZero closed because of an error.
echo Error code: %APP_EXIT%
pause
exit /b %APP_EXIT%

:python_missing
echo.
echo Python 3 was not found.
echo Install Python from https://www.python.org/downloads/windows/
echo During installation, enable "Add Python to PATH", then run this file again.
pause
exit /b 1

:setup_failed
echo.
echo CubeZero could not create its Windows environment.
echo Check your internet connection and the messages above, then try again.
pause
exit /b 1
