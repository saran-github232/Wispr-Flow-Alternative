@echo off
REM ============================================================
REM  FlowSpeak - start the app (no console window).
REM  Double-click to run. FlowSpeak lives in your system tray.
REM ============================================================
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    echo FlowSpeak is not installed yet. Running install.bat first...
    call install.bat
)

REM pythonw.exe runs without a console window.
start "" ".venv\Scripts\pythonw.exe" -m flowspeak
