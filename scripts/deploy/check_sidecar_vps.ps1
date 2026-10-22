$secpasswd = ConvertTo-SecureString "matigol1" -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential ("Administrator", $secpasswd)
$sopt = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck

$session = New-PSSession -ComputerName "80.65.211.99" -Credential $cred -UseSSL -Port 5986 -SessionOption $sopt -Authentication Basic

Invoke-Command -Session $session -ScriptBlock {
    cd C:\Slingshot
    Write-Host "=== NODE PROCESSES ON VPS ==="
    Get-CimInstance Win32_Process | Where-Object { $_.Name -like "*node*" } | Select-Object ProcessId, CommandLine | Format-Table -AutoSize

    Write-Host "=== TEST SIDECAR HEALTH :8080 ==="
    try {
        $res = Invoke-RestMethod -Uri "http://127.0.0.1:8080/health" -TimeoutSec 3 -ErrorAction Stop
        Write-Host "Sidecar :8080 Health OK: $($res | ConvertTo-Json -Compress)"
    } catch {
        Write-Host "Sidecar :8080 no responde: $($_.Exception.Message)"
    }
}

Remove-PSSession $session
