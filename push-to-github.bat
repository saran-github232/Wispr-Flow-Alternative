@echo off
REM ============================================================
REM  Push FlowSpeak to GitHub.
REM  Just double-click this file (or run it from a terminal).
REM  The repo, commit and remote are already set up for you.
REM ============================================================
setlocal
cd /d "%~dp0"

set "REPO_URL=https://github.com/saran-github232/Wispr-Flow-Alternative.git"

REM --- 1. Is Git installed? ---
where git >nul 2>&1
if errorlevel 1 (
    echo [X] Git is not installed or not on your PATH.
    echo     Install "Git for Windows" from https://git-scm.com/download/win
    echo     then run this file again.
    pause
    exit /b 1
)

REM --- 2. Make sure this folder is a git repo (fallback if .git is missing) ---
git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
    echo Initializing a new git repository...
    git init
    git config user.name "Saran"
    git config user.email "saran-github232@users.noreply.github.com"
    git add -A
    git commit -m "FlowSpeak: local-first Windows voice dictation (Python rewrite)"
)

REM --- 3. Point 'origin' at the target repo (safe to re-run) ---
git remote get-url origin >nul 2>&1
if errorlevel 1 (
    git remote add origin "%REPO_URL%"
) else (
    git remote set-url origin "%REPO_URL%"
)

REM --- 4. Make sure the branch is called main ---
git branch -M main

echo.
echo Pushing to %REPO_URL%
echo (A GitHub sign-in window may appear the first time.)
echo.
git push -u origin main
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
    echo [OK] Done. Your project is now on GitHub:
    echo      https://github.com/saran-github232/Wispr-Flow-Alternative
) else (
    echo [!] Push did not complete ^(exit code %RC%^).
    echo     * "rejected / non-fast-forward": the repo already has commits.
    echo       Run:  git pull --rebase origin main   then run this file again.
    echo     * Asked for a password: use a GitHub Personal Access Token,
    echo       or sign in when the browser window appears.
)
echo.
pause
endlocal
