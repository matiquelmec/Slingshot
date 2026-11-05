$secpasswd = ConvertTo-SecureString "matigol1" -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential ("Administrator", $secpasswd)
$sopt = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck

$session = New-PSSession -ComputerName "80.65.211.99" -Credential $cred -UseSSL -Port 5986 -SessionOption $sopt -Authentication Basic

Invoke-Command -Session $session -ScriptBlock {
    cd C:\Slingshot
    Write-Host "=== deploy_audit.log ==="
    if (Test-Path "deploy_audit.log") {
        Get-Item "deploy_audit.log" | Select-Object LastWriteTime, Length
        Get-Content "deploy_audit.log" -Tail 40
    } else {
        Write-Host "deploy_audit.log does not exist"
    }
}

Remove-PSSession $session
