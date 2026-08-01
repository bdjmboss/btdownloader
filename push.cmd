@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ========================================
echo   Git Pull + Push Retry
echo ========================================
echo.

:RETRY
echo Step 1: Pull rebase...
git pull --rebase origin main 2>&1
if %errorLevel% neq 0 (
    echo Pull failed, waiting 30s and retry...
    ping -n 31 127.0.0.1 >nul
    goto RETRY
)

echo.
echo Step 2: Push...
git push origin main 2>&1
if %errorLevel% neq 0 (
    echo Push failed, waiting 30s and retry...
    ping -n 31 127.0.0.1 >nul
    goto RETRY
)

echo.
echo SUCCESS!
pause
