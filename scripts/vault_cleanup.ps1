# Slingshot v10.0 Sovereign — Apex Vault Cleanup Script (PowerShell)
# Mantenimiento Institucional: Sincroniza la bóveda y limpia residuos de ejecución.

Write-Host "  ============================================" -ForegroundColor Cyan
Write-Host "       SLINGSHOT v10.0 - APEX CLEANUP        " -ForegroundColor Cyan
Write-Host "  ============================================" -ForegroundColor Cyan
Write-Host ""

# 1. Limpiar caches de Python y Compilación
Write-Host "  [1/4] Purgando __pycache__ y residuos .pyc ..." -ForegroundColor Yellow
Get-ChildItem -Path $PSScriptRoot\.. -Include __pycache__, *.pyc -Recurse -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
Write-Host "        OK." -ForegroundColor Green

# 2. Saneamiento de /tmp (Preservando Auditoría)
Write-Host "  [2/4] Saneando /tmp (Respetando Reportes Vivos) ..." -ForegroundColor Yellow
if (Test-Path "$PSScriptRoot\..\tmp") {
    # Borramos logs rotados pero dejamos el reporte de backtest y logs activos
    Get-ChildItem -Path "$PSScriptRoot\..\tmp" -Exclude "backtest_report_BTCUSDT.json", "slingshot.log", "data" -ErrorAction SilentlyContinue | Remove-Item -Force
}
Write-Host "        OK." -ForegroundColor Green

# 3. Mantenimiento de la Bóveda Legacy
Write-Host "  [3/4] Verificando Integridad de la Bóveda (.vault_v9_legacy) ..." -ForegroundColor Yellow
if (!(Test-Path "$PSScriptRoot\..\.vault_v9_legacy")) {
    New-Item -ItemType Directory -Path "$PSScriptRoot\..\.vault_v9_legacy" -Force | Out-Null
}
Write-Host "        OK." -ForegroundColor Green

# 4. Limpieza de Frontend (Next.js)
Write-Host "  [4/4] Limpiando Cache de Aplicación (.next/cache) ..." -ForegroundColor Yellow
if (Test-Path "$PSScriptRoot\..\.next\cache") {
    Remove-Item -Path "$PSScriptRoot\..\.next\cache" -Recurse -Force -ErrorAction SilentlyContinue
}
Write-Host "        OK." -ForegroundColor Green

Write-Host ""
Write-Host "  ✅ TERMINAL v10.0 OPTIMIZADA Y LISTA PARA EJECUCIÓN." -ForegroundColor Green
Write-Host ""
