# Slingshot v4.6 Platinum — OS Optimizer (PowerShell)
# Eleva la prioridad del motor de trading y la IA local para minimizar latencia en trading HFT.

$TradingProcess = Get-Process -Name "python" -ErrorAction SilentlyContinue
$AIProcess = Get-Process -Name "ollama" -ErrorAction SilentlyContinue

if ($TradingProcess) {
    $TradingProcess.PriorityClass = 'High'
    Write-Host "[SLINGSHOT] Motor Python elevado a prioridad: HIGH" -ForegroundColor Green
} else {
    Write-Host "[WARNING] Motor Python no detectado. Ejecuta primero Slingshot." -ForegroundColor Yellow
}

if ($AIProcess) {
    $AIProcess.PriorityClass = 'AboveNormal'
    Write-Host "[SLINGSHOT] Ollama elevado a prioridad: ABOVE NORMAL" -ForegroundColor Green
} else {
    Write-Host "[WARNING] Ollama no detectado. Asegúrate de que el servidor local esté activo." -ForegroundColor Yellow
}

Write-Host "`nSlingshot v4.6: CPU Priorizada para Trading e IA Local." -ForegroundColor Cyan
