$secpasswd = ConvertTo-SecureString "matigol1" -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential ("Administrator", $secpasswd)
$sopt = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck

$session = New-PSSession -ComputerName "80.65.211.99" -Credential $cred -UseSSL -Port 5986 -SessionOption $sopt -Authentication Basic

Invoke-Command -Session $session -ScriptBlock {
    $conn = Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue
    if ($conn) {
        Write-Host "Puerto 8080 abierto por PID: $($conn.OwningProcess)"
        Get-Process -Id $conn.OwningProcess | Select-Object Id, ProcessName, Path, StartTime | Format-List
    } else {
        Write-Host "Puerto 8080 no está en escucha."
    }

    # Revisar contenido de sidecar/index.js en el VPS
    Write-Host "=== Primeras 15 líneas de C:\Slingshot\sidecar\index.js en VPS ==="
    Get-Content "C:\Slingshot\sidecar\index.js" -TotalCount 15
    Write-Host "=== Líneas 100-115 de C:\Slingshot\sidecar\index.js en VPS ==="
    Get-Content "C:\Slingshot\sidecar\index.js" | Select-Object -Skip 99 -First 16
}

Remove-PSSession $session
