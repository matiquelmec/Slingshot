$secpasswd = ConvertTo-SecureString "matigol1" -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential ("Administrator", $secpasswd)
$sopt = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck

$session = New-PSSession -ComputerName "80.65.211.99" -Credential $cred -UseSSL -Port 5986 -SessionOption $sopt -Authentication Basic

Invoke-Command -Session $session -ScriptBlock {
    $settingsBot = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    Set-ScheduledTask -TaskName "SlingshotBot" -Settings $settingsBot -User "Administrator" -Password "matigol1"

    Write-Host "=== POST-UPDATE SLINGSHOTBOT ==="
    $task = Get-ScheduledTask -TaskName "SlingshotBot"
    [PSCustomObject]@{
        TaskName = $task.TaskName
        ExecutionTimeLimit = $task.Settings.ExecutionTimeLimit
        RestartInterval = $task.Settings.RestartInterval
        RestartCount = $task.Settings.RestartCount
        State = $task.State
    } | Format-Table -AutoSize
}

Remove-PSSession $session
