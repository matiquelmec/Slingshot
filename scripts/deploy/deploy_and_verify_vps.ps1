<#
.SYNOPSIS
    Script de Despliegue y Certificacion en Vivo para el VPS de Produccion Slingshot (SOP-125/126).
#>

$ErrorActionPreference = "Stop"

$vpsIp   = if ($env:SLINGSHOT_VPS_IP)   { $env:SLINGSHOT_VPS_IP }   else { "80.65.211.99" }
$vpsPort = if ($env:SLINGSHOT_VPS_PORT) { [int]$env:SLINGSHOT_VPS_PORT } else { 5986 }
$vpsUser = if ($env:SLINGSHOT_VPS_USER) { $env:SLINGSHOT_VPS_USER } else { "Administrator" }
$vpsPass = if ($env:SLINGSHOT_VPS_PASS) { $env:SLINGSHOT_VPS_PASS } else { "matigol1" }

Write-Host "`n>>> [KRONOS] Conectando al VPS de Produccion ($vpsIp`:$vpsPort)..." -ForegroundColor Cyan

$secPass = ConvertTo-SecureString $vpsPass -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential ($vpsUser, $secPass)
$sOpt = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck

$session = New-PSSession -ComputerName $vpsIp -Port $vpsPort -Credential $cred -UseSSL -Authentication Basic -SessionOption $sOpt

try {
    Invoke-Command -Session $session -ScriptBlock {
        Write-Host "`n=======================================================" -ForegroundColor Cyan
        Write-Host "[1/4] SINCRONIZANDO REPOSITORIO CON ORIGIN/MAIN..." -ForegroundColor Cyan
        Write-Host "=======================================================" -ForegroundColor Cyan
        Set-Location "C:\Slingshot"
        git fetch origin main 2>&1 | Out-String | Write-Host
        $pullOut = git pull origin main 2>&1 | Out-String
        Write-Host $pullOut
        $commitHash = git rev-parse --short HEAD
        $commitMsg  = git log -1 --pretty=%B
        Write-Host "Commit activo en VPS: $commitHash $commitMsg" -ForegroundColor Green

        Write-Host "`n=======================================================" -ForegroundColor Cyan
        Write-Host "[2/4] RECICLANDO FASTAPI BACKEND Y SIDECAR HFT..." -ForegroundColor Cyan
        Write-Host "=======================================================" -ForegroundColor Cyan

        # Detener tarea innecesaria SlingshotFrontend (next dev en el VPS) para liberar CPU/RAM
        Disable-ScheduledTask -TaskName "SlingshotFrontend" -ErrorAction SilentlyContinue | Out-Null
        Stop-ScheduledTask -TaskName "SlingshotFrontend" -ErrorAction SilentlyContinue | Out-Null
        Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "next.*dev|start-server\.js" } | ForEach-Object {
            Write-Host "Deteniendo proceso huérfano Next.js Dev en VPS PID: $($_.ProcessId)" -ForegroundColor Yellow
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }

        # Terminar procesos Uvicorn existentes (SlingshotBot run_slingshot_service.bat levantará 1 instancia limpia)
        $uvicornProcs = Get-CimInstance Win32_Process | Where-Object { $_.Name -match "python" -and $_.CommandLine -match "uvicorn|engine\.api\.main" }
        foreach ($p in $uvicornProcs) {
            Write-Host "Terminando proceso previo Uvicorn PID: $($p.ProcessId)" -ForegroundColor Yellow
            Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
        }

        # Terminar proceso Sidecar previo
        $sidecarProcs = Get-CimInstance Win32_Process | Where-Object { $_.Name -match "node" -and $_.CommandLine -match "sidecar" }
        foreach ($s in $sidecarProcs) {
            Write-Host "Terminando proceso previo Sidecar PID: $($s.ProcessId)" -ForegroundColor Yellow
            Stop-Process -Id $s.ProcessId -Force -ErrorAction SilentlyContinue
        }

        Start-Sleep -Seconds 4

        # Si por alguna razon SlingshotBot no estaba corriendo, asegurar 1 instancia de Uvicorn via WMI
        $checkUv = Get-CimInstance Win32_Process | Where-Object { $_.Name -match "python" -and $_.CommandLine -match "uvicorn|engine\.api\.main" }
        if (-not $checkUv) {
            $pythonExe = "C:\Program Files\Python312\python.exe"
            if (-not (Test-Path $pythonExe)) { $pythonExe = "python" }
            $null = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
                CommandLine = "`"$pythonExe`" -m uvicorn engine.api.main:app --host 0.0.0.0 --port 8000"
                CurrentDirectory = "C:\Slingshot"
            }
        }

        # Iniciar Sidecar de forma desacoplada via WMI
        if (Test-Path "C:\Slingshot\sidecar\index.js") {
            $nodeExe = "C:\Program Files\nodejs\node.exe"
            if (-not (Test-Path $nodeExe)) { $nodeExe = "node.exe" }
            $null = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
                CommandLine = "`"$nodeExe`" C:\Slingshot\sidecar\index.js"
                CurrentDirectory = "C:\Slingshot"
            }
        }

        Write-Host "`n=======================================================" -ForegroundColor Cyan
        Write-Host "[3/4] AUDITORIA DE SALUD HTTP (:8000 y :8080)..." -ForegroundColor Cyan
        Write-Host "=======================================================" -ForegroundColor Cyan

        $apiOk = $false
        for ($i = 1; $i -le 8; $i++) {
            Start-Sleep -Seconds 4
            $sw = [System.Diagnostics.Stopwatch]::StartNew()
            try {
                $health8000 = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/health" -UseBasicParsing -TimeoutSec 8
                $sw.Stop()
                Write-Host "[OK] FastAPI Health (:8000) en $($sw.ElapsedMilliseconds)ms: $($health8000.Content)" -ForegroundColor Green
                $apiOk = $true
                break
            } catch {
                Write-Host "  [Intento $i/8] Esperando inicializacion de FastAPI (:8000)..." -ForegroundColor Yellow
            }
        }
        if (-not $apiOk) {
            Write-Host "[ERROR] FastAPI (:8000) no respondio tras 8 intentos." -ForegroundColor Red
        }

        # Verificar también /api/v1/diagnostic/BTCUSDT?timeframe=1h
        $swDiag = [System.Diagnostics.Stopwatch]::StartNew()
        try {
            $diag1h = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/diagnostic/BTCUSDT?timeframe=1h" -TimeoutSec 10
            $swDiag.Stop()
            Write-Host "[OK] Diagnostic 1H (:8000) en $($swDiag.ElapsedMilliseconds)ms (Candles: $($diag1h.candles.Count), Regime: $($diag1h.tactical.market_regime))" -ForegroundColor Green
        } catch {
            Write-Host "[WARN] Diagnostic 1H fallo: $($_.Exception.Message)" -ForegroundColor Yellow
        }

        $sw2 = [System.Diagnostics.Stopwatch]::StartNew()
        try {
            $health8080 = Invoke-WebRequest -Uri "http://127.0.0.1:8080/health" -UseBasicParsing -TimeoutSec 5
            $sw2.Stop()
            Write-Host "[OK] Sidecar Health (:8080) en $($sw2.ElapsedMilliseconds)ms: $($health8080.Content)" -ForegroundColor Green
        } catch {
            Write-Host "[WARN] Sidecar (:8080) no respondio: $($_.Exception.Message)" -ForegroundColor Yellow
        }

        Write-Host "`n=======================================================" -ForegroundColor Cyan
        Write-Host "[4/4] ESTADO DE LA TRIADA OPERATIVA..." -ForegroundColor Cyan
        Write-Host "=======================================================" -ForegroundColor Cyan
        Get-Process -Name "python", "node", "terminal64" -ErrorAction SilentlyContinue | Select-Object Id, ProcessName, WorkingSet64, StartTime | Format-Table -AutoSize
    }
} finally {
    Remove-PSSession -Session $session -ErrorAction SilentlyContinue
    Write-Host "`n>>> [KRONOS] Sesion remota cerrada. Auditoria completada.`n" -ForegroundColor Cyan
}
