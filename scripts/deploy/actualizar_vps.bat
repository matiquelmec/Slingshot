@echo off
title SLINGSHOT TRADING - ACTUALIZACION CANONICA VPS
color 0B
echo ==============================================================================
echo  SLINGSHOT v60.0 APEX QUANTUM FORTRESS - AUTO-UPDATE VPS
echo ==============================================================================
echo.
echo [1/3] Navegando al directorio de instalacion en C:\Slingshot...
cd /d C:\Slingshot

echo [2/3] Descargando ultimos commits certificados desde GitHub (origin/main)...
git fetch origin main
git reset --hard origin/main

echo [3/3] Iniciando el Motor Cuantitativo Uvicorn en 0.0.0.0:8000...
call .venv\Scripts\activate.bat
python -m uvicorn engine.api.main:app --host 0.0.0.0 --port 8000
pause
