$secpasswd = ConvertTo-SecureString "matigol1" -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential ("Administrator", $secpasswd)
$sopt = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck

$session = New-PSSession -ComputerName "80.65.211.99" -Credential $cred -UseSSL -Port 5986 -SessionOption $sopt -Authentication Basic

Invoke-Command -Session $session -ScriptBlock {
    cd C:\Slingshot

    Write-Host "=== 1. TRUNCANDO Y ARCHIVANDO LOG GIGANTE (1.46 GB) ==="
    $srvLog = "C:\Slingshot\logs\slingshot_service.log"
    if (Test-Path $srvLog) {
        $sizeMB = (Get-Item $srvLog).Length / 1MB
        Write-Host "Tamaño actual de slingshot_service.log: $([math]::Round($sizeMB, 2)) MB"
        if ($sizeMB -gt 50) {
            # Guardar ultimas 1000 lineas
            $tail = Get-Content $srvLog -Tail 1000
            $tail | Out-File -FilePath "$srvLog.bak" -Encoding utf8
            # Truncar a archivo limpio
            "[$((Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))] [MAINTENANCE] Log truncado preventivamente desde $([math]::Round($sizeMB, 2)) MB" | Out-File -FilePath $srvLog -Encoding utf8
            Write-Host "slingshot_service.log truncado exitosamente a < 1KB."
        }
    }

    Write-Host "=== 2. INICIANDO SLINGSHOTBOT (SCHEDULED TASK) ==="
    # Asegurar que ningun proceso colgado bloquee el puerto 8000
    Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*engine.api.main:app*" } | ForEach-Object {
        Write-Host "Terminando proceso huerfano PID $($_.ProcessId)"
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }

    # Iniciar la tarea programada SlingshotBot
    Start-ScheduledTask -TaskName "SlingshotBot"
    Write-Host "Tarea SlingshotBot iniciada. Esperando 12 segundos para estabilizacion..."
    Start-Sleep -Seconds 12

    Write-Host "=== 3. VERIFICACION DE PROCESOS ACTIVOS ==="
    Get-Process | Where-Object { $_.ProcessName -like "*python*" -or $_.ProcessName -like "*node*" -or $_.ProcessName -like "*terminal*" } | Select-Object Id, ProcessName, WorkingSet64, StartTime | Format-Table -AutoSize

    Write-Host "=== 4. VERIFICACION DE HEALTHCHECK HTTP ==="
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/health" -TimeoutSec 10 -ErrorAction Stop
        Write-Host "[SUCCESS] /api/v1/health responde 200 OK: $($health | ConvertTo-Json -Compress)" -ForegroundColor Green
    } catch {
        Write-Host "[ERROR] /api/v1/health no respondio: $($_.Exception.Message)" -ForegroundColor Red
        if (Test-Path "C:\Slingshot\logs\slingshot_service.log") {
            Write-Host "Ultimas lineas de slingshot_service.log:"
            Get-Content "C:\Slingshot\logs\slingshot_service.log" -Tail 25
        }
    }
}

Remove-PSSession $session
