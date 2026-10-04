
$secpasswd = ConvertTo-SecureString "matigol1" -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential ("Administrator", $secpasswd)
$sopt = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck

$session = New-PSSession -ComputerName "80.65.211.99" -Credential $cred -UseSSL -Port 5986 -SessionOption $sopt -Authentication Basic

Invoke-Command -Session $session -ScriptBlock {
    cd C:\Slingshot
    # Comprobar arrancar_slingshot.bat
    Get-Content arrancar_slingshot.bat -Head 15
    # Matar cualquier python remanente
    Get-Process | Where-Object { $_.ProcessName -like "*python*" } | Stop-Process -Force -ErrorAction SilentlyContinue

    # Lanzar proceso en background desacoplado usando WMI / ScheduledTask / Start-Process
    $action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c C:\Slingshot\arrancar_slingshot.bat" -WorkingDirectory "C:\Slingshot"
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddSeconds(5)
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    
    # Registrar o arrancar inmediatamente
    Register-ScheduledTask -TaskName "SlingshotAutonomousEngine" -Action $action -Trigger $trigger -Principal $principal -Force
    Start-ScheduledTask -TaskName "SlingshotAutonomousEngine"
    Start-Sleep -Seconds 3
    Get-ScheduledTask -TaskName "SlingshotAutonomousEngine" | Select-Object TaskName, State
}

Remove-PSSession $session
