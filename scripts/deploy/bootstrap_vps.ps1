# ==============================================================================
# SLINGSHOT v42.0 APEX TITAN — BOOTSTRAP TOTAL AUTOMATIZADO WINDOWS SERVER
# ==============================================================================
$ErrorActionPreference = "Continue"
Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host "🚀 INICIANDO INSTALACION AUTOMATICA TOTAL DE SLINGSHOT v42.0" -ForegroundColor Cyan
Write-Host "==============================================================================" -ForegroundColor Cyan

# 1. Instalar Python 3.12 silenciosamente si no existe
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "⬇️ Descargando e instalando Python 3.12 automaticamente..." -ForegroundColor Yellow
    $pyUrl = "https://www.python.org/ftp/python/3.12.4/python-3.12.4-amd64.exe"
    $pyPath = "$env:TEMP\python_setup.exe"
    Invoke-WebRequest -Uri $pyUrl -OutFile $pyPath
    Start-Process -FilePath $pyPath -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1 Include_test=0" -Wait
    Remove-Item $pyPath -Force -ErrorAction SilentlyContinue
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    Write-Host "✅ Python 3.12 instalado con exito." -ForegroundColor Green
} else {
    Write-Host "✅ Python ya esta instalado." -ForegroundColor Green
}

# 2. Instalar Git silenciosamente si no existe
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "⬇️ Descargando e instalando Git para Windows automaticamente..." -ForegroundColor Yellow
    $gitUrl = "https://github.com/git-for-windows/git/releases/download/v2.45.2.windows.1/Git-2.45.2-64-bit.exe"
    $gitPath = "$env:TEMP\git_setup.exe"
    Invoke-WebRequest -Uri $gitUrl -OutFile $gitPath
    Start-Process -FilePath $gitPath -ArgumentList "/VERYSILENT /NORESTART /NOCANCEL /SP-" -Wait
    Remove-Item $gitPath -Force -ErrorAction SilentlyContinue
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    Write-Host "✅ Git instalado con exito." -ForegroundColor Green
} else {
    Write-Host "✅ Git ya esta instalado." -ForegroundColor Green
}

# 3. Habilitar OpenSSH Server para gestion remota por CLI
try {
    Write-Host "🔒 Habilitando servicio OpenSSH Server para administracion remota..." -ForegroundColor Yellow
    Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0 -ErrorAction SilentlyContinue
    Start-Service sshd -ErrorAction SilentlyContinue
    Set-Service -Name sshd -StartupType 'Automatic' -ErrorAction SilentlyContinue
    New-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -DisplayName 'OpenSSH Server (sshd)' -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22 -ErrorAction SilentlyContinue
    Write-Host "✅ OpenSSH Server activo en puerto 22." -ForegroundColor Green
} catch {
    Write-Host "ℹ️ Servicio SSH no requirio cambios." -ForegroundColor DarkGray
}

# 4. Clonar repositorio en C:\Slingshot
cd C:\
if (-not (Test-Path "C:\Slingshot")) {
    Write-Host "📦 Clonando repositorio Slingshot v42.0..." -ForegroundColor Yellow
    & "git" clone https://github.com/matiquelmec/Slingshot.git
}
cd C:\Slingshot
& "git" checkout cleanup-v1
& "git" pull origin cleanup-v1

# 5. Ejecutar instalacion del entorno y QA Tests
powershell -ExecutionPolicy Bypass -File .\scripts\deploy\setup_vps_windows.ps1
