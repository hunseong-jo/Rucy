@echo off
chcp 65001 >nul
title Rucy AI - PC Git Sync (Option A)

:: Repository: https://github.com/hunseong-jo/Rucy.git

echo ========================================================
echo       Rucy AI PC Git Sync Script (Option A)
echo ========================================================
echo.

:: Move to project root directory
cd /d "C:\Users\user\my-agent"

echo [1/4] Checking Git repository status in %CD%...
git status -s

echo.
echo [2/4] Staging local changes (memories, history, codebase)...
git add .

git diff --cached --quiet
if %errorlevel% neq 0 (
    echo Committing local changes...
    set TIMESTAMP=%DATE% %TIME%
    git commit -m "Auto sync from PC [%DATE% %TIME%]"
) else (
    echo No local changes to commit.
)

:: Detect current branch name
set BRANCH=main
for /f "delims=" %%b in ('git rev-parse --abbrev-ref HEAD 2^>nul') do set BRANCH=%%b

echo.
echo [3/4] Pulling remote updates from GitHub (branch: %BRANCH%)...
git pull --rebase origin %BRANCH% 2>nul
if %errorlevel% neq 0 (
    echo Rebase pull skipped or not needed, attempting normal pull...
    git pull origin %BRANCH% 2>nul
)

echo.
echo [4/4] Pushing updates to GitHub (branch: %BRANCH%)...
git push origin %BRANCH%
if %errorlevel% equ 0 (
    echo.
    echo ========================================================
    echo       PC Git Sync Completed Successfully!
    echo ========================================================
) else (
    echo.
    echo [ERROR] Push failed! Check your GitHub connection or credentials.
)

echo.
pause
