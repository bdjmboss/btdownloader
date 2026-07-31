@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ========================================
echo   Git Push Retry
echo ========================================
echo.

:RETRY
echo Trying to push...
git push 2>&1
if %errorLevel% neq 0 (
    echo Failed, waiting 30s and retry...
    timeout /t 30 /nobreak >nul
    goto RETRY
)

echo.
echo SUCCESS!
pause
