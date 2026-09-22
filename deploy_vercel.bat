@echo off
title Deploy Middleout-Lattice to Vercel
cd /d "%~dp0"
echo ============================================================
echo   ⚡ Deploy Middleout-Lattice to Vercel Cloud
echo   Patent-Pending Lossless Compressor Serverless Portal
echo ============================================================
echo.
echo Checking for npx / vercel CLI...
where npx >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] npx is not found. Please install Node.js (https://nodejs.org) to deploy via CLI.
    echo Alternatively, push this git repository to GitHub and import it on https://vercel.com/new
    pause
    exit /b 1
)

echo.
echo Choose deployment mode:
echo   [1] Deploy Production (npx vercel --prod)
echo   [2] Deploy Preview / Setup (npx vercel)
echo   [3] Exit
echo.
set /p choice="Enter choice [1, 2, or 3]: "

if "%choice%"=="1" (
    echo.
    echo Deploying to Vercel Production...
    npx vercel --prod
) else if "%choice%"=="2" (
    echo.
    echo Deploying to Vercel Preview...
    npx vercel
) else (
    echo Exiting.
)

pause
