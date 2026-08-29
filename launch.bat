@echo off
chcp 65001 >nul
title Slingshot Apex Sovereign -- Master Launcher
color 0A

echo ===============================================================================
echo       SLINGSHOT v22.3 APEX SOVEREIGN -- MASTER LAUNCHER (DELTA / OMEGA)          
echo ===============================================================================
echo.

cd /d "%~dp0"

echo [OMEGA] Realizando barrido forense de puertos (3000, 8000)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000') do taskkill /f /pid %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000') do taskkill /f /pid %%a >nul 2>&1
echo [OMEGA] Limpieza exitosa. Zona libre de colisiones.
echo.

echo [DELTA] Encendiendo Launcher Unificado (start.ps1)...
start "Slingshot Core" powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0start.ps1"
echo.

echo [SISTEMA] Satelites en orbita. Abriendo consola tactica en 5 segundos...
timeout /t 5 >nul
start http://localhost:3000

echo.
echo ===============================================================================
echo  INICIALIZACION COMPLETADA CON EXITO.
echo  Puedes minimizar esta ventana.
echo ===============================================================================
pause >nul
