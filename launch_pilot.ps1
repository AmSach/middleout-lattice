# Middleout-Lattice: Enterprise Pilot Server PowerShell Launcher
Set-Location -Path $PSScriptRoot
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  ⚡ Middleout-Lattice: Enterprise Pilot Server Launcher" -ForegroundColor Cyan
Write-Host "  Patent-Pending Next-Gen Lossless Compressor" -ForegroundColor DarkCyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Starting secure pilot server on http://localhost:8080 ..." -ForegroundColor Green

python pilot_server.py --port 8080
