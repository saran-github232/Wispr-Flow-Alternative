@echo off
REM ============================================================
REM  FlowSpeak - start in DEBUG mode (keeps a console open and
REM  prints logs). Use this if something isn't working.
REM ============================================================
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo FlowSpeak is not installed yet. Run install.bat first.
    pause
    exit /b 1
)

set "FLOWSPEAK_DEBUG=1"
".venv\Scripts\python.exe" -m flowspeak
echo.
echo FlowSpeak exited. Review the log above if it crashed.
pause
endlocal
