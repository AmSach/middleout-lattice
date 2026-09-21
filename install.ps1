# ===========================================================================
# Middleout-Lattice Windows Installation Script
# ===========================================================================

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Installing Middleout-Lattice CLI & Python API" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 1. Check Python installation
$python = Get-Command python.exe -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Error "Python was not found on your system PATH. Please install Python 3.10+ before running this installer."
    Exit 1
}

$pyVersion = python.exe -V 2>&1
Write-Host "Found Python: $pyVersion" -ForegroundColor Green

# 2. Set up Python Virtual Environment
Write-Host "`n[1/3] Setting up Python virtual environment (.venv)..." -ForegroundColor Yellow
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
& .venv\Scripts\pip install --upgrade pip
& .venv\Scripts\pip install -r requirements.txt

# 3. Handle C++ Compilation / Pre-built Binaries
Write-Host "`n[2/3] Checking C++ build environment..." -ForegroundColor Yellow
$cmake = Get-Command cmake -ErrorAction SilentlyContinue
$msbuild = Get-Command msbuild -ErrorAction SilentlyContinue
$make = Get-Command mingw32-make -ErrorAction SilentlyContinue

$compiled = $false
if ($cmake -and ($msbuild -or $make)) {
    Write-Host "C++ compilation environment found. Attempting to build from source..." -ForegroundColor Green
    try {
        New-Item -ItemType Directory -Force -Path "engine/build" | Out-Null
        Push-Location engine/build
        if ($make) {
            & cmake .. -G "MinGW Makefiles" -DCMAKE_BUILD_TYPE=Release
            & cmake --build . -j $env:NUMBER_OF_PROCESSORS
        } else {
            & cmake .. -DCMAKE_BUILD_TYPE=Release
            & cmake --build . --config Release -j $env:NUMBER_OF_PROCESSORS
        }
        Pop-Location
        
        # Copy compiled binaries to root
        if (Test-Path "engine/build/lattice_cli.exe") {
            Copy-Item "engine/build/lattice_cli.exe" -Destination "lattice_cli.exe" -Force
            Copy-Item "engine/build/lattice_gui.exe" -Destination "lattice_gui.exe" -Force
            Copy-Item "engine/build/liblattice_engine.dll" -Destination "liblattice_engine.dll" -Force
            $compiled = $true
        }
    } catch {
        Write-Warning "C++ build failed. Falling back to pre-built workspace binaries..."
    }
}

if (-not $compiled) {
    Write-Host "Using pre-built workspace C++ binaries." -ForegroundColor Cyan
    if (-not (Test-Path "lattice_cli.exe") -or -not (Test-Path "liblattice_engine.dll")) {
        Write-Error "Pre-built C++ binaries are missing from the workspace root!"
        Exit 1
    }
}

# 4. Add CLI to User PATH (Optional)
Write-Host "`n[3/3] Setting up CLI path..." -ForegroundColor Yellow
$currentDir = Get-Location
$pathToAdd = $currentDir.Path

# Ask user if they want to add to Path
$choice = Read-Host "Would you like to add Middleout-Lattice to your User PATH? (y/n)"
if ($choice.ToLower() -eq 'y') {
    $oldPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($oldPath -like "*$pathToAdd*") {
        Write-Host "Path already configured." -ForegroundColor Green
    } else {
        [Environment]::SetEnvironmentVariable("Path", "$oldPath;$pathToAdd", "User")
        Write-Host "Successfully added Middleout-Lattice to User PATH!" -ForegroundColor Green
        Write-Host "Please restart your terminal/PowerShell for changes to take effect." -ForegroundColor Green
    }
}

Write-Host "`n==========================================" -ForegroundColor Cyan
Write-Host "  Installation Completed Successfully!" -ForegroundColor Green
Write-Host "  - Run 'lattice_cli --help' to verify the CLI" -ForegroundColor Green
Write-Host "  - Run '.venv/Scripts/python' to use the Python API" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
