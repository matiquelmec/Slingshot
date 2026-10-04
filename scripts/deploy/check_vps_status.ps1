
$secpasswd = ConvertTo-SecureString "matigol1" -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential ("Administrator", $secpasswd)
$sopt = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck

$session = New-PSSession -ComputerName "80.65.211.99" -Credential $cred -UseSSL -Port 5986 -SessionOption $sopt -Authentication Basic

Invoke-Command -Session $session -ScriptBlock {
    cd C:\Slingshot
    # Verificar commits actuales
    git log -n 1 --oneline
    # Verificar si el supervisor o python estan corriendo
    Get-Process | Where-Object { $_.ProcessName -like "*python*" } | Select-Object Id, ProcessName, StartTime
}

Remove-PSSession $session
