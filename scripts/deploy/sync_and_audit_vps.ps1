$secpasswd = ConvertTo-SecureString "matigol1" -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential ("Administrator", $secpasswd)
$sopt = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck

$session = New-PSSession -ComputerName "80.65.211.99" -Credential $cred -UseSSL -Port 5986 -SessionOption $sopt -Authentication Basic

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
