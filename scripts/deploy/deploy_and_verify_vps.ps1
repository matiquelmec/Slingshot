# ==============================================================================
# SLINGSHOT TRADING — DEPLOY & VERIFY VPS (KRONOS SENTINEL)
# Conecta via WinRM a 80.65.211.99, sincroniza origin/main, reinicia el motor
# y verifica la salud en vivo de la triada operativa.
# ==============================================================================

$secpasswd = ConvertTo-SecureString "matigol1" -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential ("Administrator", $secpasswd)
$sopt = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck

Write-Host "`n>>> [KRONOS] Conectando al VPS de Produccion (80.65.211.99:5986)..." -ForegroundColor Cyan
$session = New-PSSession -ComputerName "80.65.211.99" -Credential $cred -UseSSL -Port 5986 -SessionOption $sopt -Authentication Basic

if (-not $session) {
    Write-Host ">>> [FAIL] No se pudo establecer sesion WinRM con el VPS." -ForegroundColor Red
    exit 1
}

try {
    Invoke-Command -Session $session -ScriptBlock {
        cd C:\Slingshot

        Write-Host "`n=======================================================" -ForegroundColor Cyan
        Write-Host "[1/4] SINCRONIZANDO REPOSITORIO CON ORIGIN/MAIN..." -ForegroundColor Cyan
        Write-Host "=======================================================" -ForegroundColor Cyan
        git fetch origin main 2>&1 | Out-String | Write-Host
        $pullOut = git pull origin main 2>&1 | Out-String
        Write-Host $pullOut
        $currentCommit = git log -n 1 --oneline
        Write-Host "Commit activo en VPS: $currentCommit" -ForegroundColor Green

        Write-Host "`n=======================================================" -ForegroundColor Cyan
        Write-Host "[2/4] REINICIANDO PROCESO FASTAPI BACKEND..." -ForegroundColor Cyan
        Write-Host "=======================================================" -ForegroundColor Cyan
        # Detener procesos viejos de uvicorn
        Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*engine.api.main:app*" } | ForEach-Object {
            Write-Host "Terminando proceso previo PID: $($_.ProcessId)"
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
        Start-Sleep -Seconds 2

        # Iniciar uvicorn con el intérprete de Python del VPS
        $pythonExe = if (Test-Path "C:\Slingshot\.venv\Scripts\python.exe") { "C:\Slingshot\.venv\Scripts\python.exe" } else { "C:\Program Files\Python312\python.exe" }
        Write-Host "Lanzando backend con: $pythonExe"
        Start-Process $pythonExe -ArgumentList "-m uvicorn engine.api.main:app --host 0.0.0.0 --port 8000" -WorkingDirectory "C:\Slingshot" -WindowStyle Hidden
        
        Write-Host "`nEsperando 15 segundos para estabilizacion de sockets..." -ForegroundColor Yellow
        Start-Sleep -Seconds 15

        Write-Host "`n=======================================================" -ForegroundColor Cyan
        Write-Host "[3/4] AUDITORIA DE SALUD HTTP (:8000)..." -ForegroundColor Cyan
        Write-Host "=======================================================" -ForegroundColor Cyan
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/health" -TimeoutSec 10 -ErrorAction Stop
            Write-Host "[OK] Endpoint Health: $($health | ConvertTo-Json -Compress)" -ForegroundColor Green
        } catch {
            Write-Host "[WARN] Endpoint Health no respondio en /api/v1/health ($($_.Exception.Message)). Probando /docs..." -ForegroundColor Yellow
            try {
                $docs = Invoke-WebRequest -Uri "http://127.0.0.1:8000/docs" -TimeoutSec 5 -ErrorAction Stop
                Write-Host "[OK] FastAPI Docs respondiendo con Status: $($docs.StatusCode)" -ForegroundColor Green
            } catch {
                Write-Host "[ERROR] El motor no responde peticiones HTTP!" -ForegroundColor Red
            }
        }

        Write-Host "`n=======================================================" -ForegroundColor Cyan
        Write-Host "[4/4] ESTADO DE LA TRIADA OPERATIVA..." -ForegroundColor Cyan
        Write-Host "=======================================================" -ForegroundColor Cyan
        $procs = Get-Process | Where-Object { $_.ProcessName -like "*python*" -or $_.ProcessName -like "*node*" -or $_.ProcessName -like "*terminal*" } | Select-Object Id, ProcessName, WorkingSet64, StartTime
        $procs | Format-Table -AutoSize | Out-String | Write-Host

        # Verificar si Sidecar o Sentinel reportan problemas
        if (Test-Path "C:\Slingshot\logs\sentinel.log") {
            Write-Host "Ultimos eventos en sentinel.log:" -ForegroundColor Gray
            Get-Content "C:\Slingshot\logs\sentinel.log" -Tail 5 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
        }
    }
} finally {
    Remove-PSSession $session
    Write-Host "`n>>> [KRONOS] Sesion remota cerrada. Auditoria completada.`n" -ForegroundColor Cyan
}
