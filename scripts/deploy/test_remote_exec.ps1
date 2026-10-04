
$secpasswd = ConvertTo-SecureString "matigol1" -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential ("Administrator", $secpasswd)
$sopt = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck

Write-Host "Intentando conectar por WinRM con Negotiate..."
try {
    $session = New-PSSession -ComputerName "80.65.211.99" -Credential $cred -UseSSL -Port 5986 -SessionOption $sopt -Authentication Negotiate
    Write-Host "Sesion establecida con Negotiate!"
    Invoke-Command -Session $session -ScriptBlock {
        cd C:\Slingshot
        git fetch origin main
        git reset --hard origin/main
        Get-Process | Where-Object { $_.ProcessName -like "*python*" } | Stop-Process -Force
        Start-Process "cmd.exe" -ArgumentList "/c arrancar_slingshot.bat" -WorkingDirectory "C:\Slingshot"
    }
    Remove-PSSession $session
    Write-Host "Completado con exito!"
} catch {
    Write-Host "Fallo Negotiate:" $_.Exception.Message
}

Write-Host "Intentando conectar por WinRM con Basic..."
try {
    $session = New-PSSession -ComputerName "80.65.211.99" -Credential $cred -UseSSL -Port 5986 -SessionOption $sopt -Authentication Basic
    Write-Host "Sesion establecida con Basic!"
    Invoke-Command -Session $session -ScriptBlock {
        cd C:\Slingshot
        git fetch origin main
        git reset --hard origin/main
        Get-Process | Where-Object { $_.ProcessName -like "*python*" } | Stop-Process -Force
        Start-Process "cmd.exe" -ArgumentList "/c arrancar_slingshot.bat" -WorkingDirectory "C:\Slingshot"
    }
    Remove-PSSession $session
    Write-Host "Completado con exito!"
} catch {
    Write-Host "Fallo Basic:" $_.Exception.Message
}
