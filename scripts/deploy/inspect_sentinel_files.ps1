$secpasswd = ConvertTo-SecureString "matigol1" -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential ("Administrator", $secpasswd)
$sopt = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck

$session = New-PSSession -ComputerName "80.65.211.99" -Credential $cred -UseSSL -Port 5986 -SessionOption $sopt -Authentication Basic

Invoke-Command -Session $session -ScriptBlock {
    cd C:\Slingshot
    Write-Host "=== run_sentinel.bat ==="
    if (Test-Path "run_sentinel.bat") { Get-Content "run_sentinel.bat" }

    Write-Host "=== run_slingshot_service.bat ==="
    if (Test-Path "run_slingshot_service.bat") { Get-Content "run_slingshot_service.bat" }

    Write-Host "=== arrancar_slingshot.bat ==="
    if (Test-Path "arrancar_slingshot.bat") { Get-Content "arrancar_slingshot.bat" }

    Write-Host "=== Any sentinel scripts in C:\Slingshot? ==="
    Get-ChildItem -Path "C:\Slingshot" -Filter "*sentinel*" -Recurse -Depth 2 | Select-Object FullName
}

Remove-PSSession $session
