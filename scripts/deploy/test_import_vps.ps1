$secpasswd = ConvertTo-SecureString "matigol1" -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential ("Administrator", $secpasswd)
$sopt = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck

$session = New-PSSession -ComputerName "80.65.211.99" -Credential $cred -UseSSL -Port 5986 -SessionOption $sopt -Authentication Basic

Invoke-Command -Session $session -ScriptBlock {
    cd C:\Slingshot
    Write-Host "=== ARCHIVOS EN C:\Slingshot\logs ==="
    Get-ChildItem -Path "logs" | Select-Object Name, LastWriteTime, Length | Format-Table -AutoSize

    Write-Host "=== TEST RAPIDO: EJECUTAR PYTHON ENGINE MANUALMENTE PARA VER SI HAY ERROR DE IMPORT O SINTAXIS ==="
    & ".\.venv\Scripts\python.exe" -c "import engine.api.main; print('Import engine.api.main OK!')"
}

Remove-PSSession $session
