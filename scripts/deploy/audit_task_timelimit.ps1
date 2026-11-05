$secpasswd = ConvertTo-SecureString "matigol1" -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential ("Administrator", $secpasswd)
$sopt = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck

$session = New-PSSession -ComputerName "80.65.211.99" -Credential $cred -UseSSL -Port 5986 -SessionOption $sopt -Authentication Basic

Invoke-Command -Session $session -ScriptBlock {
    Write-Host "=== SCHEDULED TASKS EXECUTION TIME LIMIT AUDIT ==="
    Get-ScheduledTask | Where-Object { $_.TaskName -match "Slingshot" } | ForEach-Object {
        [PSCustomObject]@{
            TaskName = $_.TaskName
            ExecutionTimeLimit = $_.Settings.ExecutionTimeLimit
            RestartOnFailure = $_.Settings.RestartOnFailure
            RestartInterval = $_.Settings.RestartInterval
            RestartCount = $_.Settings.RestartCount
            MultipleInstances = $_.Settings.MultipleInstancesPolicy
        }
    } | Format-Table -AutoSize
}

Remove-PSSession $session
