Write-Host "========================================" -ForegroundColor Cyan
Write-Host "BT APK Build Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/5] Enable WSL..." -ForegroundColor Yellow
try {
    Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux -NoRestart -ErrorAction Stop
    Write-Host "  WSL enabled" -ForegroundColor Green
} catch {
    Write-Host "  Failed: $_" -ForegroundColor Red
    Write-Host "  Run as Administrator!" -ForegroundColor Red
    exit 1
}

Write-Host "[2/5] Enable VirtualMachinePlatform..." -ForegroundColor Yellow
try {
    Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -NoRestart -ErrorAction Stop
    Write-Host "  VirtualMachinePlatform enabled" -ForegroundColor Green
} catch {
    Write-Host "  Failed (ok): $_" -ForegroundColor Red
}

Write-Host "[3/5] Set WSL2 default..." -ForegroundColor Yellow
wsl --set-default-version 2 2>$null

Write-Host "[4/5] Install Ubuntu..." -ForegroundColor Yellow
wsl --install -d Ubuntu 2>$null

Write-Host "[5/5] Create desktop shortcut..." -ForegroundColor Yellow
$dt = [Environment]::GetFolderPath("Desktop")
$sc = Join-Path $dt "BT-APK-Build.lnk"
$sh = New-Object -ComObject WScript.Shell
$s = $sh.CreateShortcut($sc)
$s.TargetPath = "powershell.exe"
$s.Arguments = '-Command "cd c:\tools\Hermes-windows\workspace\Bt下载软件\bt_phone; wsl -d Ubuntu bash build_apk.sh"'
$s.WorkingDirectory = "c:\tools\Hermes-windows\workspace\Bt下载软件\bt_phone"
$s.Description = "Build BT APK"
$s.Save()
Write-Host "  Shortcut: $sc" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Done! Need restart." -ForegroundColor Cyan
Write-Host "After restart:" -ForegroundColor White
Write-Host "  1. Open Ubuntu (Start menu)" -ForegroundColor White
Write-Host "  2. Set username/password" -ForegroundColor White
Write-Host "  3. Double-click desktop shortcut" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Cyan
