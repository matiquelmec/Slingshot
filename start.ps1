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
Write-Host "       SLINGSHOT GEN 1 - LAUNCHER            " -ForegroundColor Cyan
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

# --- Backend (FastAPI en puerto 8000) ---
Write-Host "  [1/2] Iniciando Backend  (http://localhost:8000)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList `
    "-ExecutionPolicy", "Bypass", `
    "-NoExit", `
    "-Command", "Set-Location -LiteralPath '$PSScriptRoot'; . .\.venv\Scripts\Activate.ps1; python -m uvicorn engine.api.main:app --host 0.0.0.0 --port 8000 --reload"

# Esperar 3s para dar tiempo al backend de levantar antes del frontend
Start-Sleep -Seconds 3

# --- Frontend (Next.js en puerto 3000) ---
# Usa 'node ./node_modules/.bin/next dev' para evitar el wrapper .cmd de Windows
# que genera el prompt '¿Desea terminar el trabajo por lotes?' en PowerShell
Write-Host "  [2/2] Iniciando Frontend (http://localhost:3000)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList `
    "-ExecutionPolicy", "Bypass", `
    "-NoExit", `
    "-Command", "Set-Location -LiteralPath '$PSScriptRoot'; node .\node_modules\next\dist\bin\next dev"

Write-Host ""
Write-Host "  OK - Slingshot Gen 1 iniciado correctamente" -ForegroundColor Green
Write-Host "     Backend  -> http://localhost:8000/docs" -ForegroundColor White
Write-Host "     Frontend -> http://localhost:3000" -ForegroundColor White
Write-Host ""
Write-Host "  NOTA: Desactiva el VPN para que Binance funcione." -ForegroundColor DarkYellow
Write-Host ""
