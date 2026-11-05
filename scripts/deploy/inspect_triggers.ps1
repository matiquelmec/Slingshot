$secpasswd = ConvertTo-SecureString "matigol1" -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential ("Administrator", $secpasswd)
$sopt = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck

$session = New-PSSession -ComputerName "80.65.211.99" -Credential $cred -UseSSL -Port 5986 -SessionOption $sopt -Authentication Basic

Invoke-Command -Session $session -ScriptBlock {
    Write-Host "=== TRIGGERS OF SLINGSHOTBOT ==="
    (Get-ScheduledTask -TaskName "SlingshotBot").Triggers | Format-List *

    Write-Host "=== TRIGGERS OF SLINGSHOTSENTINEL ==="
    (Get-ScheduledTask -TaskName "SlingshotSentinel").Triggers | Format-List *
}

Remove-PSSession $session
