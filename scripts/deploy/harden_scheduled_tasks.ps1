$secpasswd = ConvertTo-SecureString "matigol1" -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential ("Administrator", $secpasswd)
$sopt = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck

$session = New-PSSession -ComputerName "80.65.211.99" -Credential $cred -UseSSL -Port 5986 -SessionOption $sopt -Authentication Basic

Invoke-Command -Session $session -ScriptBlock {
    Write-Host "=== BLINDANDO TAREAS PROGRAMADAS A TIEMPO INFINITO (ZERO 72-HOUR LIMIT) ==="
    
    # 1. Configurar SlingshotBot: Sin limite de tiempo (Zero/Infinite), Auto-reinicio ante fallo
    $settingsBot = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    Set-ScheduledTask -TaskName "SlingshotBot" -Settings $settingsBot
    Write-Host "[OK] SlingshotBot configurado con ExecutionTimeLimit = INFINITO y RestartOnFailure = 999"

    # 2. Configurar SlingshotAutonomousEngine
    $settingsAuto = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    Set-ScheduledTask -TaskName "SlingshotAutonomousEngine" -Settings $settingsAuto
    Write-Host "[OK] SlingshotAutonomousEngine configurado con ExecutionTimeLimit = INFINITO"

    # 3. Comprobar resultado actualizado
    Get-ScheduledTask | Where-Object { $_.TaskName -match "Slingshot" } | ForEach-Object {
        [PSCustomObject]@{
            TaskName = $_.TaskName
            ExecutionTimeLimit = $_.Settings.ExecutionTimeLimit
            RestartInterval = $_.Settings.RestartInterval
            RestartCount = $_.Settings.RestartCount
            MultipleInstances = $_.Settings.MultipleInstancesPolicy
        }
    } | Format-Table -AutoSize
}

Remove-PSSession $session
