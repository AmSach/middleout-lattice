@echo off
title Middleout-Lattice Enterprise Pilot Server
cd /d "%~dp0"
echo ============================================================
echo   Middleout-Lattice: Enterprise Pilot Server Launcher
echo   Patent-Pending Next-Gen Lossless Compressor
echo ============================================================
echo Starting secure pilot server on http://localhost:8080 ...
python pilot_server.py --port 8080
pause
