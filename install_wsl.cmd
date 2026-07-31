@echo off
echo ========================================
echo   BT APK Builder - WSL Setup
echo ========================================
echo.

net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ERROR: Not running as Administrator!
    echo.
    echo Please RIGHT-CLICK this file and select:
    echo   "Run as administrator"
    echo.
    pause
    exit /b 1
)

echo [1/4] Enabling WSL feature...
dism /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart

echo [2/4] Enabling VirtualMachinePlatform...
dism /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart

echo [3/4] Setting WSL2 as default...
wsl --update 2>nul
wsl --set-default-version 2

echo [4/4] Installing Ubuntu...
wsl --install -d Ubuntu

echo.
echo ========================================
echo DONE! Need to restart computer.
echo After restart:
echo   1. Open Ubuntu from Start Menu
echo   2. Set username and password
echo   3. Run build_apk.sh inside WSL
echo ========================================
echo.
pause
shutdown /r /t 10
