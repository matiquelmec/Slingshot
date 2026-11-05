# ==============================================================================
# SLINGSHOT TRADING — DEPLOY & VERIFY VPS (KRONOS SENTINEL v42.6)
# Conecta via WinRM a 80.65.211.99, sincroniza origin/main, recicla procesos
# desacoplados via WMI/ScheduledTask y certifica salud HTTP (:8000 y :8080).
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
        Write-Host "[2/4] RECICLANDO FASTAPI BACKEND Y SIDECAR HFT..." -ForegroundColor Cyan
        Write-Host "=======================================================" -ForegroundColor Cyan
        # Detener procesos viejos de uvicorn (run_slingshot_service.bat lo relanza automáticamente en 3s)
        Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*engine.api.main:app*" } | ForEach-Object {
            Write-Host "Terminando proceso previo Uvicorn PID: $($_.ProcessId)"
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }

        # Reciclar Sidecar via WMI Win32_Process.Create para persistir fuera de WinRM
        Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*sidecar*" } | ForEach-Object {
            Write-Host "Terminando proceso previo Sidecar PID: $($_.ProcessId)"
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
        Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
            CommandLine = "C:\Program Files\nodejs\node.exe C:\Slingshot\sidecar\index.js"
            CurrentDirectory = "C:\Slingshot"
        } | Out-Null

        # Si SlingshotBot no estuviera corriendo, iniciarlo por tarea programada
        Start-ScheduledTask -TaskName "SlingshotBot" -ErrorAction SilentlyContinue

        Write-Host "`n=======================================================" -ForegroundColor Cyan
        Write-Host "[3/4] AUDITORIA DE SALUD HTTP (:8000 y :8080)..." -ForegroundColor Cyan
        Write-Host "=======================================================" -ForegroundColor Cyan
        $ok8000 = $false
        for ($i = 1; $i -le 8; $i++) {
            Start-Sleep -Seconds 5
            $sw = [System.Diagnostics.Stopwatch]::StartNew()
            try {
                $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/health" -TimeoutSec 5 -ErrorAction Stop
                $sw.Stop()
                Write-Host "[OK] FastAPI Health (:8000) en $($sw.ElapsedMilliseconds)ms: $($health | ConvertTo-Json -Compress)" -ForegroundColor Green
                $ok8000 = $true
                break
            } catch {
                Write-Host "  [Intento $i/8] Esperando inicializacion de FastAPI (:8000)..." -ForegroundColor Yellow
            }
        }
        if (-not $ok8000) {
            Write-Host "[ERROR] El motor FastAPI (:8000) no respondio tras 40s!" -ForegroundColor Red
        }

        $swSide = [System.Diagnostics.Stopwatch]::StartNew()
        try {
            $sideHealth = Invoke-RestMethod -Uri "http://127.0.0.1:8080/health" -TimeoutSec 5 -ErrorAction Stop
            $swSide.Stop()
            Write-Host "[OK] Sidecar Health (:8080) en $($swSide.ElapsedMilliseconds)ms: $($sideHealth | ConvertTo-Json -Compress)" -ForegroundColor Green
        } catch {
            Write-Host "[WARN] Sidecar (:8080) no respondio: $($_.Exception.Message)" -ForegroundColor Yellow
        }

        Write-Host "`n=======================================================" -ForegroundColor Cyan
        Write-Host "[4/4] ESTADO DE LA TRIADA OPERATIVA..." -ForegroundColor Cyan
        Write-Host "=======================================================" -ForegroundColor Cyan
        $procs = Get-Process | Where-Object { $_.ProcessName -like "*python*" -or $_.ProcessName -like "*node*" -or $_.ProcessName -like "*terminal*" } | Select-Object Id, ProcessName, WorkingSet64, StartTime
        $procs | Format-Table -AutoSize | Out-String | Write-Host
    }
} finally {
    Remove-PSSession $session
    Write-Host "`n>>> [KRONOS] Sesion remota cerrada. Auditoria completada.`n" -ForegroundColor Cyan
}
