$secpasswd = ConvertTo-SecureString "matigol1" -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential ("Administrator", $secpasswd)
$sopt = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck

$session = New-PSSession -ComputerName "80.65.211.99" -Credential $cred -UseSSL -Port 5986 -SessionOption $sopt -Authentication Basic

Invoke-Command -Session $session -ScriptBlock {
    Write-Host "=== 1. VPS UPTIME & LAST BOOT ==="
    Get-CimInstance Win32_OperatingSystem | Select-Object Caption, LastBootUpTime, @{Name="UptimeHours";Expression={[math]::round(((Get-Date) - $_.LastBootUpTime).TotalHours, 2)}} | Format-Table -AutoSize

    Write-Host "=== 2. SCHEDULED TASKS LAST RUN INFO ==="
    Get-ScheduledTask | Where-Object { $_.TaskName -match "Slingshot" } | ForEach-Object {
        $info = Get-ScheduledTaskInfo -TaskName $_.TaskName
        [PSCustomObject]@{
            TaskName = $_.TaskName
            State = $_.State
            LastRunTime = $info.LastRunTime
            LastTaskResult = $info.LastTaskResult
            NextRunTime = $info.NextRunTime
        }
    } | Format-Table -AutoSize

    Write-Host "=== 3. APPLICATION EVENT LOG CRASHES/ERRORS ON 21-OCT-2026 ==="
    Get-WinEvent -FilterHashtable @{LogName='Application'; Level=1,2; StartTime=(Get-Date "2026-10-21 17:00:00"); EndTime=(Get-Date "2026-10-21 19:00:00")} -ErrorAction SilentlyContinue | Select-Object TimeCreated, ProviderName, Id, Message | Format-Table -AutoSize

    Write-Host "=== 4. SYSTEM EVENT LOG ON 21-OCT-2026 ==="
    Get-WinEvent -FilterHashtable @{LogName='System'; StartTime=(Get-Date "2026-10-21 17:40:00"); EndTime=(Get-Date "2026-10-21 17:55:00")} -MaxEvents 15 -ErrorAction SilentlyContinue | Select-Object TimeCreated, ProviderName, Id, Message | Format-Table -AutoSize

    Write-Host "=== 5. DEFINITION OF SLINGSHOT TASKS ==="
    Get-ScheduledTask | Where-Object { $_.TaskName -match "Slingshot" } | ForEach-Object {
        Write-Host "Task: $($_.TaskName)"
        $_.Actions | ForEach-Object { Write-Host "   Execute: $($_.Execute) $($_.Arguments)" }
        $_.Triggers | ForEach-Object { Write-Host "   Trigger: $($_.Enabled) Repetition: $($_.Repetition.Interval)" }
    }
}

Remove-PSSession $session
