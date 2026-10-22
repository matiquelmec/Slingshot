$secpasswd = ConvertTo-SecureString "matigol1" -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential ("Administrator", $secpasswd)
$sopt = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck

$session = New-PSSession -ComputerName "80.65.211.99" -Credential $cred -UseSSL -Port 5986 -SessionOption $sopt -Authentication Basic

Invoke-Command -Session $session -ScriptBlock {
    cd C:\Slingshot
    Write-Host "=== 1. DISK SPACE ==="
    Get-PSDrive C | Select-Object Name, Used, Free, @{Name="FreeGB";Expression={[math]::round($_.Free/1GB, 2)}}, @{Name="UsedGB";Expression={[math]::round($_.Used/1GB, 2)}} | Format-Table -AutoSize

    Write-Host "=== 2. PHP VULNERABILITY CHECK (CONTABO ADVISORY) ==="
    $phpCmd = Get-Command php -ErrorAction SilentlyContinue
    if ($phpCmd) {
        Write-Host "PHP detectado en PATH: $($phpCmd.Source)"
        php -v
    } else {
        Write-Host "PHP NO esta en el PATH del sistema."
    }
    $phpDirs = Get-ChildItem -Path C:\ -Recurse -Depth 2 -Filter "*php*" -ErrorAction SilentlyContinue | Select-Object FullName
    if ($phpDirs) {
        Write-Host "Carpetas/archivos PHP encontrados:"
        $phpDirs | ForEach-Object { Write-Host " - $($_.FullName)" }
    } else {
        Write-Host "No se encontraron directorios de PHP en C:\ (raiz/subdirectorios)."
    }

    Write-Host "=== 3. WEB SERVERS / PHP RUNTIMES (IIS, APACHE, NGINX) ==="
    Get-Process | Where-Object { $_.ProcessName -match "httpd|apache|nginx|w3wp|php" } | Format-Table Id, ProcessName, WorkingSet64 -AutoSize
    Get-Service | Where-Object { $_.Name -match "w3svc|apache|nginx|php" } | Format-Table Name, DisplayName, Status, StartType -AutoSize

    Write-Host "=== 4. WINDOWS SERVICES & SCHEDULED TASKS ==="
    Get-Service | Where-Object { $_.Name -match "Slingshot|Sentinel" } | Format-Table Name, DisplayName, Status, StartType -AutoSize
    Get-ScheduledTask | Where-Object { $_.TaskName -match "Slingshot|Sentinel" } | Format-Table TaskName, State, TaskPath -AutoSize

    Write-Host "=== 5. LAST 50 LINES OF SLINGSHOT.LOG ==="
    if (Test-Path "C:\Slingshot\logs\slingshot.log") {
        Get-Content "C:\Slingshot\logs\slingshot.log" -Tail 50
    }

    Write-Host "=== 6. LAST 50 LINES OF SLINGSHOT_SERVICE.LOG ==="
    if (Test-Path "C:\Slingshot\logs\slingshot_service.log") {
        Get-Content "C:\Slingshot\logs\slingshot_service.log" -Tail 50
    }

    Write-Host "=== 7. SYSTEM EVENT LOG (ERRORS IN LAST 48 HOURS) ==="
    Get-WinEvent -FilterHashtable @{LogName='System'; Level=1,2; StartTime=(Get-Date).AddHours(-48)} -MaxEvents 10 -ErrorAction SilentlyContinue | Select-Object TimeCreated, ProviderName, Id, Message | Format-Table -AutoSize
}

Remove-PSSession $session
