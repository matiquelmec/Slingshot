$secpasswd = ConvertTo-SecureString "matigol1" -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential ("Administrator", $secpasswd)
$sopt = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck

$session = New-PSSession -ComputerName "80.65.211.99" -Credential $cred -UseSSL -Port 5986 -SessionOption $sopt -Authentication Basic

Invoke-Command -Session $session -ScriptBlock {
    Write-Host "=== 1. ULTIMAS LINEAS DE SENTINEL.LOG ==="
    Get-Content "C:\Slingshot\logs\sentinel.log" -Tail 10

    Write-Host "=== 2. PROCESOS PYTHON Y NODE ACTIVOS ==="
    Get-Process | Where-Object { $_.ProcessName -like "*python*" -or $_.ProcessName -like "*node*" } | Select-Object Id, ProcessName, WorkingSet64, StartTime | Format-Table -AutoSize

    Write-Host "=== 3. COMMIT ACTUAL EN VPS ==="
    cd C:\Slingshot
    git log -n 1 --oneline
}

Remove-PSSession $session
