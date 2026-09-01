# ============================================================
# SLINGSHOT GEN 1 - Launcher Unificado
# ============================================================
# Uso: ./start.ps1
#      (Si da error de política: powershell -ExecutionPolicy Bypass -File start.ps1)
# ============================================================

# Forzar UTF-8 en la consola del launcher
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host ""
Write-Host "  ============================================" -ForegroundColor Cyan
Write-Host "        SLINGSHOT v28.0 APEX MULTIPLIER       " -ForegroundColor Cyan
Write-Host "  ============================================" -ForegroundColor Cyan
Write-Host ""

# Verificar que el .venv existe antes de continuar
if (-Not (Test-Path "$PSScriptRoot\.venv\Scripts\Activate.ps1")) {
    Write-Host "  [ERROR] No se encontro el entorno virtual .venv" -ForegroundColor Red
    Write-Host "          Ejecuta: python -m venv .venv && pip install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}

# Verificar que node_modules existe
if (-Not (Test-Path "$PSScriptRoot\node_modules")) {
    Write-Host "  [ERROR] No se encontro node_modules" -ForegroundColor Red
    Write-Host "          Ejecuta: npm install" -ForegroundColor Yellow
    exit 1
}

# --- Chequeo de Cerebro Local (Ollama) ---
Write-Host "  [0/2] Verificando servidor Ollama (Gemma)..." -ForegroundColor Yellow
try {
    $ollama = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -Method Get -ErrorAction Stop
    Write-Host "        OK - Conectado a Ollama Local." -ForegroundColor Green
} catch {
    Write-Host "  [ALERTA ROJA] Ollama no esta corriendo en localhost:11434." -ForegroundColor Red
    Write-Host "                El sistema de IA tactica estara degradado o inoperativo." -ForegroundColor DarkYellow
    Write-Host "                Levanta la app de Ollama para tener inferencia Tactica humana." -ForegroundColor DarkYellow
    Start-Sleep -Seconds 2
}

# --- Sidecar HFT (Node.js en puerto 8080) ---
Write-Host "  [0.5/2] Iniciando HFT Sidecar (http://localhost:8080)..." -ForegroundColor Yellow
$userProfile = $env:USERPROFILE
$sidecarPath = "$userProfile\.gemini\config\skills\slingshot_hft_sidecar\scripts\index.js"
if (Test-Path $sidecarPath) {
    # Usamos cmd /c start node para máxima compatibilidad con caracteres especiales en Windows
    Start-Process cmd -ArgumentList "/c start /min node `"$sidecarPath`""
} else {
    Write-Host "  [ALERTA] No se encontro la ruta global del Sidecar HFT." -ForegroundColor DarkYellow
}

# --- Backend (FastAPI en puerto 8000) ---
Write-Host "  [1/2] Iniciando Backend  (http://localhost:8000)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList `
    "-ExecutionPolicy", "Bypass", `
    "-NoExit", `
    "-Command", "Set-Location -LiteralPath '$PSScriptRoot'; .\.venv\Scripts\python.exe -m uvicorn engine.api.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir engine/api --reload-dir engine/core --reload-dir engine/indicators --reload-dir engine/risk --reload-dir engine/execution --reload-dir engine/ml --reload-dir engine/router --reload-dir engine/workers --reload-dir engine/strategies"

# Esperar 3s para dar tiempo al backend de levantar antes del frontend
Start-Sleep -Seconds 3

# --- Frontend (Next.js en puerto 3000) ---
# Auto-recuperación: Si .next existe pero tiene manifiestos corruptos o vacíos, purgar preventivamente
if (Test-Path "$PSScriptRoot\.next") {
    $manifestFiles = Get-ChildItem -Path "$PSScriptRoot\.next" -Recurse -Filter "*manifest*.json" -ErrorAction SilentlyContinue
    $corruptFound = $false
    foreach ($mf in $manifestFiles) {
        if ($mf.Length -eq 0) {
            $corruptFound = $true
            break
        }
    }
    if ($corruptFound) {
        Write-Host "  [AUTO-HEAL] Detectado manifiesto corrupto en .next. Purgando cache..." -ForegroundColor DarkYellow
        Remove-Item -Path "$PSScriptRoot\.next" -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# Usa 'node ./node_modules/.bin/next dev' para evitar el wrapper .cmd de Windows
# que genera el prompt '¿Desea terminar el trabajo por lotes?' en PowerShell
Write-Host "  [2/2] Iniciando Frontend (http://localhost:3000)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList `
    "-ExecutionPolicy", "Bypass", `
    "-NoExit", `
    "-Command", "Set-Location -LiteralPath '$PSScriptRoot'; node .\node_modules\next\dist\bin\next dev"

# --- Optimización de Latencia Institucional (v11.1.0) ---
Write-Host "  [3/3] Optimizando prioridad del S.O. para trading..." -ForegroundColor Yellow
Start-Sleep -Seconds 5
if (Test-Path "$PSScriptRoot\scripts\optimize_os.ps1") {
    powershell -ExecutionPolicy Bypass -File "$PSScriptRoot\scripts\optimize_os.ps1"
}

Write-Host ""
Write-Host "  ✅ SLINGSHOT GEN 1 OPERATIVO" -ForegroundColor Green
Write-Host "     Backend  -> http://localhost:8000/docs" -ForegroundColor White
Write-Host "     Frontend -> http://localhost:3000" -ForegroundColor White
Write-Host ""
Write-Host "  MODO: ALTA PRIORIDAD ACTIVADO" -ForegroundColor Cyan
Write-Host "  NOTA: Desactiva el VPN para que Binance funcione." -ForegroundColor DarkYellow
Write-Host ""
