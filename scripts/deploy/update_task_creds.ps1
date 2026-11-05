$secpasswd = ConvertTo-SecureString "matigol1" -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential ("Administrator", $secpasswd)
$sopt = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck

$session = New-PSSession -ComputerName "80.65.211.99" -Credential $cred -UseSSL -Port 5986 -SessionOption $sopt -Authentication Basic

Invoke-Command -Session $session -ScriptBlock {
    $xml = Export-ScheduledTask -TaskName "SlingshotBot"
    $xml = $xml -replace '<ExecutionTimeLimit>PT72H</ExecutionTimeLimit>', '<ExecutionTimeLimit>PT0S</ExecutionTimeLimit>'
    
    # Registrar pasando credenciales explícitas
    Register-ScheduledTask -TaskName "SlingshotBot" -Xml $xml -User "Administrator" -Password "matigol1" -Force
    
    Write-Host "=== VERIFICACION POST-UPDATE DE TODAS LAS TAREAS ==="
    Get-ScheduledTask | Where-Object { $_.TaskName -match "Slingshot" } | ForEach-Object {
        [PSCustomObject]@{
            TaskName = $_.TaskName
            ExecutionTimeLimit = $_.Settings.ExecutionTimeLimit
            RestartInterval = $_.Settings.RestartInterval
            RestartCount = $_.Settings.RestartCount
            State = $_.State
        }
    } | Format-Table -AutoSize
}

Remove-PSSession $session
