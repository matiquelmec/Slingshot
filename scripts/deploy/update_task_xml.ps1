$secpasswd = ConvertTo-SecureString "matigol1" -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential ("Administrator", $secpasswd)
$sopt = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck

$session = New-PSSession -ComputerName "80.65.211.99" -Credential $cred -UseSSL -Port 5986 -SessionOption $sopt -Authentication Basic

Invoke-Command -Session $session -ScriptBlock {
    $task = Get-ScheduledTask -TaskName "SlingshotBot"
    Write-Host "UserId: $($task.Principal.UserId)"
    Write-Host "LogonType: $($task.Principal.LogonType)"
    Write-Host "RunLevel: $($task.Principal.RunLevel)"

    # Actualizar via XML o exportando/re-importando con SYSTEM o Administrator
    $xml = Export-ScheduledTask -TaskName "SlingshotBot"
    $xml = $xml -replace '<ExecutionTimeLimit>PT72H</ExecutionTimeLimit>', '<ExecutionTimeLimit>PT0S</ExecutionTimeLimit>'
    $xml = $xml -replace '<RestartOnFailure>[\s\S]*?</RestartOnFailure>', ''
    # Inyectar RestartOnFailure si no esta
    if ($xml -match '<Settings>') {
        $xml = $xml -replace '<Settings>', "<Settings>`n    <RestartOnFailure>`n      <Interval>PT1M</Interval>`n      <Count>999</Count>`n    </RestartOnFailure>"
    }
    Register-ScheduledTask -TaskName "SlingshotBot" -Xml $xml -Force
    
    Write-Host "SlingshotBot ExecutionTimeLimit post-update:"
    (Get-ScheduledTask -TaskName "SlingshotBot").Settings.ExecutionTimeLimit
}

Remove-PSSession $session
