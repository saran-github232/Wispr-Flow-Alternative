@echo off
REM ============================================================
REM  FlowSpeak - one-time installer
REM  Creates a local virtual environment and installs everything.
REM  Just double-click this file once.
REM ============================================================
setlocal EnableExtensions
cd /d "%~dp0"

echo.
echo ========================================
echo   Installing FlowSpeak...
echo ========================================
echo.

REM --- Find a COMPATIBLE Python -------------------------------
REM The speech engine (faster-whisper -> ctranslate2 / onnxruntime)
REM only ships Windows wheels for Python 3.10 - 3.13. Python 3.14
REM is too new and would make pip try to compile from source and fail,
REM so we deliberately look for 3.12/3.11/3.10/3.13 first.
set "PY="
for %%V in (3.12 3.11 3.10 3.13) do if not defined PY py -%%V --version >nul 2>&1 && set "PY=py -%%V"

REM Fallback to a generic launcher if no specific version was found.
if not defined PY where py >nul 2>&1 && set "PY=py -3"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY goto no_python

REM Make sure whatever we picked is actually 3.10 - 3.13.
%PY% -c "import sys; raise SystemExit(0 if (3,10)<=sys.version_info[:2]<=(3,13) else 1)" 2>nul
if errorlevel 1 goto bad_python

echo Using Python: %PY%
%PY% --version
echo.

REM --- Create / repair the virtual environment ----------------
REM If an old .venv was built with an unsupported Python (e.g. 3.14),
REM rebuild it from scratch so the install can succeed.
if not exist ".venv\Scripts\python.exe" goto make_venv
".venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if (3,10)<=sys.version_info[:2]<=(3,13) else 1)" 2>nul
if not errorlevel 1 goto venv_ok
echo Existing .venv uses an unsupported Python - rebuilding it...
rmdir /s /q ".venv"

:make_venv
echo Creating virtual environment in .venv ...
%PY% -m venv .venv
if errorlevel 1 goto venv_fail

:venv_ok
set "VENV_PY=.venv\Scripts\python.exe"

echo.
echo Upgrading pip ...
"%VENV_PY%" -m pip install --upgrade pip

echo.
echo Installing dependencies (this can take a few minutes the first time) ...
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 goto deps_fail

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
exit /b 0

:no_python
echo [ERROR] Python was not found on your system.
echo.
echo Please install Python 3.12 from:
echo     https://www.python.org/downloads/
echo IMPORTANT: tick "Add python.exe to PATH" in the installer, then
echo run install.bat again.
echo.
pause
exit /b 1

:bad_python
echo [ERROR] The Python on your system is not compatible with FlowSpeak.
%PY% --version
echo.
echo FlowSpeak's speech engine needs Python 3.10 - 3.13. Python 3.14 is
echo too new - several components have no Windows installer for it yet,
echo which is why the dependencies failed to install.
echo.
echo Please install Python 3.12 from:
echo     https://www.python.org/downloads/
echo (tick "Add python.exe to PATH"), then run install.bat again.
echo You can keep 3.14 installed - this just uses 3.12 for FlowSpeak.
echo.
pause
exit /b 1

:venv_fail
echo [ERROR] Could not create the virtual environment.
pause
exit /b 1

:deps_fail
echo.
echo [ERROR] Dependency installation failed. Scroll up for the reason.
pause
exit /b 1

endlocal
