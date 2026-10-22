$secpasswd = ConvertTo-SecureString "matigol1" -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential ("Administrator", $secpasswd)
$sopt = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck

$session = New-PSSession -ComputerName "80.65.211.99" -Credential $cred -UseSSL -Port 5986 -SessionOption $sopt -Authentication Basic

Invoke-Command -Session $session -ScriptBlock {
    cd C:\Slingshot
    Write-Host "=== INICIANDO SIDECAR NODE.JS ==="
    # Iniciar sidecar/index.js
    Start-Process node -ArgumentList "sidecar\index.js" -WorkingDirectory "C:\Slingshot" -WindowStyle Hidden
    Start-Sleep -Seconds 3

    Write-Host "=== HEALTH CHECK SIDECAR PUERTO 8080 ==="
    try {
        $res = Invoke-RestMethod -Uri "http://127.0.0.1:8080/health" -Method Get -TimeoutSec 3
        Write-Host "SIDECAR OK: status=$($res.status), uptime=$($res.uptime)"
    } catch {
        Write-Host "Fallo en health: $($_.Exception.Message)"
    }
}

Remove-PSSession $session
