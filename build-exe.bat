@echo off
REM ============================================================
REM  FlowSpeak - build a standalone FlowSpeak.exe (optional).
REM  Produces dist\FlowSpeak.exe which runs without Python.
REM  Note: the first dictation still downloads the speech model.
REM ============================================================
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Run install.bat first.
    pause
    exit /b 1
)

set "VENV_PY=.venv\Scripts\python.exe"
"%VENV_PY%" -m pip install --upgrade pyinstaller

"%VENV_PY%" -m PyInstaller --noconfirm --clean ^
    --name FlowSpeak ^
    --windowed ^
    --icon "flowspeak\assets\flowspeak.ico" ^
    --add-data "flowspeak\assets;flowspeak\assets" ^
    --collect-all faster_whisper ^
    --collect-all ctranslate2 ^
    --collect-all tokenizers ^
    --collect-all onnxruntime ^
    run.py

echo.
echo Build complete. See dist\FlowSpeak.exe
pause
endlocal
