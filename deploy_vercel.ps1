# Deploy Middleout-Lattice to Vercel Cloud PowerShell Script
Set-Location -Path $PSScriptRoot
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  ⚡ Deploy Middleout-Lattice to Vercel Cloud" -ForegroundColor Cyan
Write-Host "  Patent-Pending Lossless Compressor Serverless Portal" -ForegroundColor DarkCyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Get-Command npx -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] npx is not found. Please install Node.js (https://nodejs.org) to deploy via CLI." -ForegroundColor Red
    Write-Host "Alternatively, push this repository to GitHub and import it on https://vercel.com/new" -ForegroundColor Yellow
    exit 1
}

Write-Host "Choose deployment mode:" -ForegroundColor White
Write-Host "  [1] Deploy Production (npx vercel --prod)" -ForegroundColor Green
Write-Host "  [2] Deploy Preview / Setup (npx vercel)" -ForegroundColor Yellow
Write-Host "  [3] Exit" -ForegroundColor DarkGray
Write-Host ""

$choice = Read-Host "Enter choice [1, 2, or 3]"

if ($choice -eq "1") {
    Write-Host "`nDeploying directly to Vercel Production..." -ForegroundColor Green
    npx vercel --prod
} elseif ($choice -eq "2") {
    Write-Host "`nDeploying to Vercel Preview..." -ForegroundColor Yellow
    npx vercel
} else {
    Write-Host "Exiting."
}
