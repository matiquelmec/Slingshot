$secpasswd = ConvertTo-SecureString "matigol1" -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential ("Administrator", $secpasswd)
$sopt = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck

$session = New-PSSession -ComputerName "80.65.211.99" -Credential $cred -UseSSL -Port 5986 -SessionOption $sopt -Authentication Basic

Invoke-Command -Session $session -ScriptBlock {
    Write-Host "=== TEST HEALTHCHECK HTTP EN VPS ==="
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/health" -TimeoutSec 10 -ErrorAction Stop
        Write-Host "HEALTHCHECK OK: $($health | ConvertTo-Json -Compress)"
    } catch {
        Write-Host "Healthcheck fallo: $($_.Exception.Message)"
        Get-Process | Where-Object { $_.ProcessName -like "*python*" } | Select-Object Id, ProcessName, WorkingSet64, StartTime | Format-Table -AutoSize
    }

    Write-Host "=== PUERTOS EN ESCUCHA EN VPS ==="
    Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -in 8000, 8080, 5986, 3000 } | Select-Object LocalAddress, LocalPort, OwningProcess | Format-Table -AutoSize
}

Remove-PSSession $session
