$secpasswd = ConvertTo-SecureString "matigol1" -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential ("Administrator", $secpasswd)
$sopt = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck

$session = New-PSSession -ComputerName "80.65.211.99" -Credential $cred -UseSSL -Port 5986 -SessionOption $sopt -Authentication Basic

Invoke-Command -Session $session -ScriptBlock {
    cd C:\Slingshot
    Write-Host "=== ÚLTIMAS 30 LÍNEAS DE slingshot_service.log ==="
    Get-Content "C:\Slingshot\logs\slingshot_service.log" -Tail 30

    Write-Host "=== LÍNEA DE COMANDOS DE LOS PROCESOS PYTHON ==="
    Get-CimInstance Win32_Process | Where-Object { $_.Name -like "*python*" } | Select-Object ProcessId, CommandLine | Format-List
}

Remove-PSSession $session
