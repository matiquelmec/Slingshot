# ==============================================================================
# SLINGSHOT v42.0 APEX TITAN — AUTO-DEPLOY SCRIPT PARA WINDOWS SERVER VPS
# ==============================================================================

Write-Host ""
Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host "INICIANDO AUTO-DESPLIEGUE OFICIAL: SLINGSHOT v42.0 EN WINDOWS SERVER VPS" -ForegroundColor Cyan
Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Verificar Python 3.12
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Python no esta instalado o no fue agregado al PATH." -ForegroundColor Red
    Write-Host "Por favor instala Python 3.12 marcando la casilla 'Add python.exe to PATH'." -ForegroundColor Yellow
    exit 1
}
Write-Host "Python detectado: $pythonVersion" -ForegroundColor Green

# 2. Crear Entorno Virtual .venv
if (-not (Test-Path ".venv")) {
    Write-Host "Creando entorno virtual aislado (.venv)..." -ForegroundColor Yellow
    python -m venv .venv
}
Write-Host "Entorno virtual listo." -ForegroundColor Green

# 3. Activar y Actualizar Pip
Write-Host "Instalando dependencias institucionales (Polars, FastAPI, PyTest, MetaTrader5)..." -ForegroundColor Yellow
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\pip.exe install -r requirements.txt
& .\.venv\Scripts\pip.exe install MetaTrader5

# 4. Crear archivo .env si no existe
if (-not (Test-Path ".env")) {
    Write-Host "Generando plantilla oficial .env para Bitunix y MT5..." -ForegroundColor Yellow
    @"
# ==============================================================================
# SLINGSHOT v42.0 APEX TITAN — CONFIGURACION DUAL EN PRODUCCION
# ==============================================================================
DRY_RUN=false

# --- BITUNIX CUENTA PRINCIPAL ---
BITUNIX_API_KEY=tu_api_key_aqui
BITUNIX_SECRET_KEY=tu_secret_key_aqui

# --- FOREX / ORO: FTMO METATRADER 5 ---
FTMO_ACCOUNT_SIZE=100000
FTMO_PHASE=PHASE_1
FTMO_WATCHLIST=XAUUSD,XAGUSD,US100,US500,USOIL,GER40,EURUSD,USDJPY,USDCAD,GBPJPY

# --- ALERTAS TELEGRAM (OPCIONAL) ---
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# --- SERVIDOR WEB ---
PORT=8000
HOST=0.0.0.0
"@ | Out-File -FilePath ".env" -Encoding utf8
    Write-Host "Archivo .env generado. Recuerda colocar tus API Keys de Bitunix." -ForegroundColor Magenta
}

# 5. Crear Lanzador .BAT para el Escritorio
$launcherContent = @"
@echo off
title SLINGSHOT TRADING DUAL ENGINE (BITUNIX + MT5)
color 0A
cd /d %~dp0
call .venv\Scripts\activate.bat
python -m uvicorn engine.api.main:app --host 0.0.0.0 --port 8000
pause
"@
$launcherContent | Out-File -FilePath "arrancar_slingshot.bat" -Encoding ascii
Write-Host "Lanzador 'arrancar_slingshot.bat' generado con exito." -ForegroundColor Green

# 6. Ejecutar Certificacion QA Oficial (212 Tests)
Write-Host ""
Write-Host "Ejecutando Suite Oficial de Certificacion QA en este Servidor..." -ForegroundColor Cyan
& .\.venv\Scripts\python.exe scripts/run_qa_suite.py

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "==============================================================================" -ForegroundColor Green
    Write-Host "DESPLIEGUE EXITOSO: EL SERVIDOR ESTA 100% OPERATIVO Y CERTIFICADO" -ForegroundColor Green
    Write-Host "Abre arrancar_slingshot.bat para iniciar el motor 24/7." -ForegroundColor Green
    Write-Host "==============================================================================" -ForegroundColor Green
} else {
    Write-Host "Hubo advertencias durante la certificacion. Revisa los logs arriba." -ForegroundColor Yellow
}
