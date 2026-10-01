@echo off
REM ============================================================
REM  FlowSpeak - one-time installer
REM  Creates a local virtual environment and installs everything.
REM  Just double-click this file once.
REM ============================================================
setlocal
cd /d "%~dp0"

echo.
echo ========================================
echo   Installing FlowSpeak...
echo ========================================
echo.

REM --- Find a Python 3 launcher -------------------------------
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY (
    where python >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo [ERROR] Python was not found on your system.
    echo.
    echo Please install Python 3.10 or newer from:
    echo     https://www.python.org/downloads/
    echo IMPORTANT: tick "Add python.exe to PATH" in the installer.
    echo.
    pause
    exit /b 1
)

echo Using Python: %PY%
%PY% --version
echo.

REM --- Create the virtual environment -------------------------
if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment in .venv ...
    %PY% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Could not create the virtual environment.
        pause
        exit /b 1
    )
) else (
    echo Virtual environment already exists - reusing it.
)

set "VENV_PY=.venv\Scripts\python.exe"

echo.
echo Upgrading pip ...
"%VENV_PY%" -m pip install --upgrade pip

echo.
echo Installing dependencies (this can take a few minutes the first time) ...
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERROR] Dependency installation failed. Scroll up for the reason.
    pause
    exit /b 1
)

echo.
echo ========================================
echo   FlowSpeak installed successfully!
echo ========================================
echo.
echo   Start it any time by double-clicking:  run.bat
echo   (Optional) make a desktop shortcut:    right-click create_shortcut.ps1
echo                                          ^> Run with PowerShell
echo.
echo   The first time you dictate, a ~150 MB speech model downloads
echo   automatically. After that it works fully offline.
echo.
pause
endlocal
