
$secpasswd = ConvertTo-SecureString "matigol1" -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential ("Administrator", $secpasswd)
$sopt = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck

$session = New-PSSession -ComputerName "80.65.211.99" -Credential $cred -UseSSL -Port 5986 -SessionOption $sopt -Authentication Basic

Invoke-Command -Session $session -ScriptBlock {
    # Hacer peticion local dentro del VPS a 127.0.0.1:8000
    try {
        $res = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/metrics" -TimeoutSec 10
        $res | ConvertTo-Json -Depth 2
    } catch {
        Write-Host "Local error:" $_.Exception.Message
    }
}

Remove-PSSession $session
