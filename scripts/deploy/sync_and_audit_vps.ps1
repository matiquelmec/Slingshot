$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$envFile = Join-Path $repoRoot ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+?)\s*=\s*(.*)\s*$') {
            $k = $matches[1].Trim()
            $v = $matches[2].Trim().Trim('"').Trim("'")
            if (-not [Environment]::GetEnvironmentVariable($k)) {
                [Environment]::SetEnvironmentVariable($k, $v, "Process")
            }
        }
    }
}

$vpsIp   = if ($env:SLINGSHOT_VPS_IP)   { $env:SLINGSHOT_VPS_IP }   else { "80.65.211.99" }
$vpsPort = if ($env:SLINGSHOT_VPS_PORT) { [int]$env:SLINGSHOT_VPS_PORT } else { 5986 }
$vpsUser = if ($env:SLINGSHOT_VPS_USER) { $env:SLINGSHOT_VPS_USER } else { "Administrator" }
$vpsPass = $env:SLINGSHOT_VPS_PASS
if (-not $vpsPass) {
    Write-Error "Falta SLINGSHOT_VPS_PASS en variables de entorno o .env. Operación abortada por seguridad."
    exit 1
}

$secpasswd = ConvertTo-SecureString $vpsPass -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential ($vpsUser, $secpasswd)
$sopt = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck

$session = New-PSSession -ComputerName $vpsIp -Credential $cred -UseSSL -Port $vpsPort -SessionOption $sopt -Authentication Basic

Invoke-Command -Session $session -ScriptBlock {
    cd C:\Slingshot
    Write-Host "=== 1. ARCHIVOS DE LOG EN EL VPS ==="
    Get-ChildItem -Path "C:\Slingshot\logs" -Filter "*.log" | Select-Object Name, LastWriteTime, Length | Format-Table -AutoSize

    Write-Host "=== 2. PROCESOS ACTIVOS EN EL VPS ==="
    Get-Process | Where-Object { $_.ProcessName -like "*python*" -or $_.ProcessName -like "*node*" -or $_.ProcessName -like "*terminal*" } | Select-Object Id, ProcessName, WorkingSet64, StartTime | Format-Table -AutoSize

    Write-Host "=== 3. ÚLTIMO LOG DE SENTINEL ==="
    if (Test-Path "C:\Slingshot\logs\sentinel.log") {
        Get-Content "C:\Slingshot\logs\sentinel.log" -Tail 15
    }

    Write-Host "=== 4. LOGS DE SIDECAR (SI EXISTEN) ==="
    $sidecarLog = Get-ChildItem -Path "C:\Slingshot\logs" -Filter "*sidecar*.log" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($sidecarLog) {
        Write-Host "Leyendo: $($sidecarLog.Name)"
        Get-Content $sidecarLog.FullName -Tail 20
    }

    Write-Host "=== 5. ESTADO DEL DEMONIO SLINGSHOT ==="
    $daemonLog = Get-ChildItem -Path "C:\Slingshot\logs" -Filter "*daemon*.log" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($daemonLog) {
        Write-Host "Leyendo: $($daemonLog.Name)"
        Get-Content $daemonLog.FullName -Tail 20
    }
}

Remove-PSSession $session
