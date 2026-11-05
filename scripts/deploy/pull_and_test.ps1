$secpasswd = ConvertTo-SecureString "matigol1" -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential ("Administrator", $secpasswd)
$sopt = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck

$session = New-PSSession -ComputerName "80.65.211.99" -Credential $cred -UseSSL -Port 5986 -SessionOption $sopt -Authentication Basic

Invoke-Command -Session $session -ScriptBlock {
    cd C:\Slingshot
    git pull origin main
    Write-Host "Commit actual en VPS: $(git log -n 1 --oneline)"

    Write-Host "`n=== EJECUTANDO CI_CD_SENTINEL ==="
    & ".\.venv\Scripts\python.exe" engine\workers\ci_cd_sentinel.py
}

Remove-PSSession $session
