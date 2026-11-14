$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$envFile = Join-Path $repoRoot ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+?)\s*=\s*(.*)\s*$') {
            $k = $matches[1].Trim()
            $v = $matches[2].Trim().Trim('"').Trim("'")
            if (-not [Environment]::GetEnvironmentVariable($k)) {
                [Environment]::SetEnvironmentVariable($k, $v, "Process")
            }
        }
    }
}

$vpsIp   = if ($env:SLINGSHOT_VPS_IP)   { $env:SLINGSHOT_VPS_IP }   else { "80.65.211.99" }
$vpsPort = if ($env:SLINGSHOT_VPS_PORT) { [int]$env:SLINGSHOT_VPS_PORT } else { 5986 }
$vpsUser = if ($env:SLINGSHOT_VPS_USER) { $env:SLINGSHOT_VPS_USER } else { "Administrator" }
$vpsPass = $env:SLINGSHOT_VPS_PASS
if (-not $vpsPass) {
    Write-Error "Falta SLINGSHOT_VPS_PASS en variables de entorno o .env. Operación abortada por seguridad."
    exit 1
}

$secpasswd = ConvertTo-SecureString $vpsPass -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential ($vpsUser, $secpasswd)
$sopt = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck

$session = New-PSSession -ComputerName $vpsIp -Credential $cred -UseSSL -Port $vpsPort -SessionOption $sopt -Authentication Basic

Invoke-Command -Session $session -ScriptBlock {
    cd C:\Slingshot
    Write-Host "=== ÚLTIMAS 30 LÍNEAS DE slingshot_service.log ==="
    Get-Content "C:\Slingshot\logs\slingshot_service.log" -Tail 30

    Write-Host "=== LÍNEA DE COMANDOS DE LOS PROCESOS PYTHON ==="
    Get-CimInstance Win32_Process | Where-Object { $_.Name -like "*python*" } | Select-Object ProcessId, CommandLine | Format-List
}

Remove-PSSession $session
