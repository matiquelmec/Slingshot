$secpasswd = ConvertTo-SecureString "matigol1" -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential ("Administrator", $secpasswd)
$sopt = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck
$session = New-PSSession -ComputerName "80.65.211.99" -Credential $cred -UseSSL -Port 5986 -SessionOption $sopt -Authentication Basic

Invoke-Command -Session $session -ScriptBlock {
    cd C:\Slingshot
    git pull origin main 2>&1 | Out-String | Write-Host
    git log -n 1 --oneline
    Write-Host "=== Reiniciando motor (sentinel lo relanza si cae) ==="
    Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*engine.api.main:app*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 2
    Start-Process "C:\Program Files\Python312\python.exe" -ArgumentList "-m uvicorn engine.api.main:app --host 0.0.0.0 --port 8000" -WorkingDirectory "C:\Slingshot" -WindowStyle Hidden
    Start-Sleep -Seconds 25
    try {
        $r = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/health" -TimeoutSec 10
        Write-Host "HEALTH: $($r.status)"
    } catch { Write-Host "HEALTH FAIL: $($_.Exception.Message)" }
    Get-Process python -ErrorAction SilentlyContinue | Select-Object Id, StartTime | Format-Table -AutoSize
}
Remove-PSSession $session
