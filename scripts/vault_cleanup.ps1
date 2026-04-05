# Slingshot v5.4.3 — Vault Cleanup Script (PowerShell)
# Mantenimiento preventivo: Limpia caches y archivos temporales para evitar "drift" de datos.

Write-Host "  ============================================" -ForegroundColor Cyan
Write-Host "       SLINGSHOT - VAULT CLEANUP             " -ForegroundColor Cyan
Write-Host "  ============================================" -ForegroundColor Cyan
Write-Host ""

# 1. Limpiar caches de Python
Write-Host "  [1/4] Limpiando __pycache__ ..." -ForegroundColor Yellow
Get-ChildItem -Path $PSScriptRoot\.. -Include __pycache__ -Recurse -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
Write-Host "        OK." -ForegroundColor Green

# 2. Limpiar directorio /tmp
Write-Host "  [2/4] Vaciando /tmp ..." -ForegroundColor Yellow
if (Test-Path "$PSScriptRoot\..\tmp") {
    Get-ChildItem -Path "$PSScriptRoot\..\tmp" -Exclude "logs", "data" -ErrorAction SilentlyContinue | Remove-Item -Force
}
Write-Host "        OK." -ForegroundColor Green

# 3. Limpiar carpeta .next (Frontend Cache)
Write-Host "  [3/4] Limpiando cache de Next.js (.next) ..." -ForegroundColor Yellow
if (Test-Path "$PSScriptRoot\..\.next") {
    # No borramos todo, solo el cache si es posible, o todo para "Fresh Start"
    # Por seguridad en desarrollo borramos el cache de fetch
    if (Test-Path "$PSScriptRoot\..\.next\cache") {
        Remove-Item -Path "$PSScriptRoot\..\.next\cache" -Recurse -Force -ErrorAction SilentlyContinue
    }
}
Write-Host "        OK." -ForegroundColor Green

# 4. Limpiar Pytest Cache
Write-Host "  [4/4] Limpiando .pytest_cache ..." -ForegroundColor Yellow
if (Test-Path "$PSScriptRoot\..\.pytest_cache") {
    Remove-Item -Path "$PSScriptRoot\..\.pytest_cache" -Recurse -Force -ErrorAction SilentlyContinue
}
Write-Host "        OK." -ForegroundColor Green

Write-Host ""
Write-Host "  ✅ SISTEMA SINCRONIZADO Y LIMPIO." -ForegroundColor Green
Write-Host ""
