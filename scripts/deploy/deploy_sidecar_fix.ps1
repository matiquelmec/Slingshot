$secpasswd = ConvertTo-SecureString "matigol1" -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential ("Administrator", $secpasswd)
$sopt = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck

$session = New-PSSession -ComputerName "80.65.211.99" -Credential $cred -UseSSL -Port 5986 -SessionOption $sopt -Authentication Basic

Invoke-Command -Session $session -ScriptBlock {
    cd C:\Slingshot
    Write-Host "=== 1. PULL ORIGIN MAIN EN VPS ==="
    git pull origin main
    git log -n 1 --oneline

    Write-Host "=== 2. REINICIANDO SIDECAR CON EL NUEVO ENDPOINT /health ==="
    Get-WmiObject Win32_Process | Where-Object { $_.CommandLine -like "*sidecar/index.js*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 2
    Start-Process node -ArgumentList "sidecar\index.js" -WorkingDirectory "C:\Slingshot" -WindowStyle Hidden
    Start-Sleep -Seconds 3

    Write-Host "=== 3. TEST DIRECTO A http://127.0.0.1:8080/health ==="
    try {
        $res = Invoke-RestMethod -Uri "http://127.0.0.1:8080/health" -Method Get -TimeoutSec 3
        Write-Host "Respuesta de Sidecar Health: $($res | ConvertTo-Json)"
    } catch {
        Write-Host "Error testeando health: $_"
    }

    Write-Host "=== 4. TEST DIRECTO A http://127.0.0.1:8000/api/v1/health ==="
    try {
        $apiRes = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/health" -Method Get -TimeoutSec 5
        Write-Host "Respuesta de FastAPI Health: $($apiRes | ConvertTo-Json)"
    } catch {
        Write-Host "Error testeando FastAPI: $_"
    }
}

Remove-PSSession $session
