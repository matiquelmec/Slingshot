
$secpasswd = ConvertTo-SecureString "matigol1" -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential ("Administrator", $secpasswd)
$sopt = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck

$session = New-PSSession -ComputerName "80.65.211.99" -Credential $cred -UseSSL -Port 5986 -SessionOption $sopt -Authentication Basic

Invoke-Command -Session $session -ScriptBlock {
    # Inspeccionar telemetria Bitunix
    try {
        $res = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/bitunix/telemetry" -TimeoutSec 10
        Write-Host "BITUNIX TELEMETRY:"
        $res | ConvertTo-Json -Depth 3
    } catch {
        Write-Host "Bitunix error:" $_.Exception.Message
    }
    
    # Comprobar endpoint deploy-update en la version fresca
    try {
        $res2 = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/status" -TimeoutSec 10
        Write-Host "STATUS:"
        $res2 | ConvertTo-Json -Depth 2
    } catch {
        Write-Host "Status error:" $_.Exception.Message
    }
}

Remove-PSSession $session
