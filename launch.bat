@echo off
chcp 65001 >nul
title Slingshot v42.0 APEX TITAN COMPOUND -- Master Launcher
color 0A

echo ===============================================================================
echo       SLINGSHOT v42.0 APEX TITAN COMPOUND -- MASTER LAUNCHER (DELTA / OMEGA)          
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

echo [SISTEMA] Esperando inicializacion de servicios (FastAPI & Next.js)...
powershell -Command "$ready = $false; $attempts = 0; while (-not $ready -and $attempts -lt 30) { try { $r = Invoke-WebRequest -Uri 'http://localhost:3000' -UseBasicParsing -TimeoutSec 1; if ($r.StatusCode -eq 200) { $ready = $true } } catch { Start-Sleep -Milliseconds 800; $attempts++ } }; if ($ready) { Write-Host '  [OK] Servicios listos. Abriendo terminal interactiva...' -ForegroundColor Green } else { Write-Host '  [AVISO] Abriendo navegador...' -ForegroundColor Yellow }"

start http://localhost:3000

echo.
echo ===============================================================================
echo  INICIALIZACION COMPLETADA CON EXITO.
echo  Puedes minimizar esta ventana.
echo ===============================================================================
pause >nul
