# scripts/sentinel_watchdog.ps1
<#
=============================================================================
SLINGSHOT SENTINEL WATCHDOG 24/7 (SOP-PERPETUAL ENGINE v57.0)
=============================================================================
Supervisor infinito de auto-sanacion para Windows Server en VPS.
Monitorea cada 30 segundos:
  1. Backend FastAPI (:8000)
  2. Sidecar Ingestor HFT (:8080)
Si algun servicio falla mas de 2 veces consecutivas, lo reinicia de inmediato
y registra la incidencia en logs/sentinel.log sin perturbar el trading activo.
=============================================================================
#>

$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root

$logDir = Join-Path $root logs
if (!(Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$logFile = Join-Path $logDir sentinel.log

function Log-Sentinel($msg) {
    $timestamp = (Get-Date).ToUniversalTime().ToString(yyyy-MM-ddTHH:mm:ssZ)
    $line = [$timestamp UTC] [SENTINEL] $msg
    Write-Host $line -ForegroundColor Cyan
    Add-Content -Path $logFile -Value $line
}

Log-Sentinel === INICIANDO SLINGSHOT SENTINEL WATCHDOG 24/7 ===

$fastapiFails = 0
$sidecarFails = 0

while ($true) {
    try {
        # 1. Chequeo de Sidecar HFT (Puerto 8080)
        try {
            $hftRes = Invoke-RestMethod -Uri http://127.0.0.1:8080/health -Method Get -TimeoutSec 3 -ErrorAction Stop
            if ($hftRes.status -eq ok) {
                $sidecarFails = 0
            } else {
                $sidecarFails++
            }
        } catch {
            $sidecarFails++
        }

        if ($sidecarFails -ge 2) {
            Log-Sentinel ALERTA: HFT Sidecar caido o no responde. Reiniciando node sidecar/index.js...
            Get-WmiObject Win32_Process | Where-Object { $_.CommandLine -like *sidecar/index.js* } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
            
            $sidecarScript = Join-Path $root sidecar\index.js
            if (Test-Path $sidecarScript) {
                Start-Process cmd -ArgumentList /c start /min node $sidecarScript"
 Log-Sentinel HFT Sidecar reanudado exitosamente.
 }
 $sidecarFails = 0
 }

 # 2. Chequeo de Backend FastAPI (Puerto 8000)
 try {
 $apiRes = Invoke-RestMethod -Uri http://127.0.0.1:8000/api/health -Method Get -TimeoutSec 5 -ErrorAction Stop
 if ($apiRes.status -eq ok -or $apiRes.status -eq healthy) {
 $fastapiFails = 0
 } else {
 $fastapiFails++
 }
 } catch {
 $fastapiFails++
 }

 if ($fastapiFails -ge 2) {
 Log-Sentinel ALERTA: Backend FastAPI (:8000) caido o congelado. Reiniciando servicio...
 Get-WmiObject Win32_Process | Where-Object { $_.CommandLine -like *engine.api.main:app* } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
 
 $pyExe = Join-Path $root .venv\Scripts\python.exe
 if (!(Test-Path $pyExe)) { $pyExe = python.exe }
 
 Start-Process powershell -ArgumentList -ExecutionPolicy Bypass -NoExit -Command Set-Location -LiteralPath ''; & '' -m uvicorn engine.api.main:app --host 0.0.0.0 --port 8000 --reload
 Log-Sentinel Backend FastAPI reanudado.
 $fastapiFails = 0
 }

 } catch {
 Log-Sentinel Error en ciclo de vigilancia: $_
 }

 Start-Sleep -Seconds 30
}
