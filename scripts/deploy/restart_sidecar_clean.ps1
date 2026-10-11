$secpasswd = ConvertTo-SecureString "matigol1" -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential ("Administrator", $secpasswd)
$sopt = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck

$session = New-PSSession -ComputerName "80.65.211.99" -Credential $cred -UseSSL -Port 5986 -SessionOption $sopt -Authentication Basic

Invoke-Command -Session $session -ScriptBlock {
    Write-Host "=== 1. MATANDO PROCESO NODE ANTIGUO PID 4180 ==="
    Stop-Process -Id 4180 -Force -ErrorAction SilentlyContinue
    Get-Process -Name "node" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2

    Write-Host "=== 2. INICIANDO SIDECAR ACTUALIZADO ==="
    Start-Process node -ArgumentList "sidecar\index.js" -WorkingDirectory "C:\Slingshot" -WindowStyle Hidden
    Start-Sleep -Seconds 3

    Write-Host "=== 3. COMPROBANDO HEALTH CHECK PUERTO 8080 ==="
    try {
        $res = Invoke-RestMethod -Uri "http://127.0.0.1:8080/health" -Method Get -TimeoutSec 3
        Write-Host "SUCCESS: status=$($res.status), uptime=$($res.uptime)"
    } catch {
        Write-Host "Fallo en health: $($_.Exception.Message)"
    }

    Write-Host "=== 4. PROCESO NODE ACTUAL EN PUERTO 8080 ==="
    $conn = Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($conn) {
        Get-Process -Id $conn.OwningProcess | Select-Object Id, ProcessName, StartTime | Format-Table -AutoSize
    }
}

Remove-PSSession $session
