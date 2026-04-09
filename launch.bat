@echo off
title Slingshot Master Launcher (Delta / Omega / Sigma)
color 0A

echo ===========================================================
echo       SLINGSHOT GEN 1 v6.0 - MASTER GOLD TITANIUM          
echo ===========================================================
echo.

echo [OMEGA] Realizando barrido forense de puertos (3000, 8000)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000') do taskkill /f /pid %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000') do taskkill /f /pid %%a >nul 2>&1
echo [OMEGA] Limpieza exitosa. Zona libre de colisiones.
echo.

echo [DELTA] Encendiendo El Launcher Unificado (start.ps1)...
start "Slingshot Core" powershell -ExecutionPolicy Bypass -File ".\start.ps1"
echo.

echo [SISTEMA] Todos los satelites en orbita. Abriendo consola tactica en 5 segundos...
timeout /t 5 >nul
start http://localhost:3000

echo.
echo =========================================
echo  INICIALIZACION COMPLETADA CON EXITO.
echo  Puedes minimizar esta ventana.       
echo =========================================
pause >nul
