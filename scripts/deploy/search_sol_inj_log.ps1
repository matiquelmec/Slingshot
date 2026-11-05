$secpasswd = ConvertTo-SecureString "matigol1" -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential ("Administrator", $secpasswd)
$sopt = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck

$session = New-PSSession -ComputerName "80.65.211.99" -Credential $cred -UseSSL -Port 5986 -SessionOption $sopt -Authentication Basic

Invoke-Command -Session $session -ScriptBlock {
    cd C:\Slingshot
    Write-Host "=== BUSCANDO EN SLINGSHOT.LOG REFERENCIAS A SOLUSDT O INJUSDT ==="
    if (Test-Path "logs\slingshot.log") {
        Get-Content "logs\slingshot.log" -Tail 200 | Select-String "AUTO-LIMIT|SOP-18|BLOCKED|MARKET_SCANNER|INJUSDT|SOLUSDT" | Select-Object -Last 15
    }
}

Remove-PSSession $session
