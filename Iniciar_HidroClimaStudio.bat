@echo off
title HidroClima Studio
cd /d "%~dp0"
if exist "dist\HidroClimaStudio\HidroClimaStudio.exe" (
    start "" "dist\HidroClimaStudio\HidroClimaStudio.exe"
    exit /b 0
)
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" run_hidroclima.py
) else (
    python run_hidroclima.py
)
pause
