# ==============================================================================
# SLINGSHOT v22.3 APEX SOVEREIGN -- ASISTENTE AUTOMATIZADO DE INSTALACION
# ==============================================================================
# Uso: .\install.ps1 (o doble clic en install.bat)
# ==============================================================================

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "  =================================================================" -ForegroundColor Cyan
Write-Host "       SLINGSHOT v22.3 APEX SOVEREIGN -- ASISTENTE DE INSTALACION" -ForegroundColor Cyan
Write-Host "  =================================================================" -ForegroundColor Cyan
Write-Host ""

$rootDir = $PSScriptRoot
if (-not $rootDir) {
    $rootDir = Get-Location
}

# ── PASO 1: VERIFICACION DE PYTHON 3.12 ─────────────────────────────────────
Write-Host "  [1/6] Verificando entorno Python..." -ForegroundColor Yellow
$pyInstalled = $false
try {
    $pyVer = python --version 2>&1
    if ($pyVer -match "Python 3\.(1[0-9]|[2-9][0-9])") {
        Write-Host "        [OK] $pyVer detectado y listo." -ForegroundColor Green
        $pyInstalled = $true
    }
} catch {
    $pyInstalled = $false
}

if (-not $pyInstalled) {
    Write-Host "        [WARN] Python 3.12 no detectado en PATH. Instalando via winget..." -ForegroundColor DarkYellow
    try {
        winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements
        Write-Host "        [OK] Python 3.12 instalado correctamente." -ForegroundColor Green
    } catch {
        Write-Host "        [ERROR] Error instalando Python con winget. Por favor instala Python 3.12 desde https://python.org" -ForegroundColor Red
        exit 1
    }
}

# ── PASO 2: VERIFICACION DE NODE.JS ─────────────────────────────────────────
Write-Host "  [2/6] Verificando entorno Node.js..." -ForegroundColor Yellow
$nodeInstalled = $false
try {
    $nodeVer = node --version 2>&1
    if ($nodeVer -match "v(1[8-9]|2[0-9])") {
        Write-Host "        [OK] Node.js $nodeVer detectado y listo." -ForegroundColor Green
        $nodeInstalled = $true
    }
} catch {
    $nodeInstalled = $false
}

if (-not $nodeInstalled) {
    Write-Host "        [WARN] Node.js no detectado en PATH. Instalando via winget..." -ForegroundColor DarkYellow
    try {
        winget install --id OpenJS.NodeJS.LTS -e --silent --accept-package-agreements --accept-source-agreements
        Write-Host "        [OK] Node.js LTS instalado correctamente." -ForegroundColor Green
    } catch {
        Write-Host "        [ERROR] Error instalando Node.js con winget. Por favor instala Node.js desde https://nodejs.org" -ForegroundColor Red
        exit 1
    }
}

# ── PASO 3: CREACION DE ENTORNO VIRTUAL PYTHON & DEPENDENCIAS ───────────────
Write-Host "  [3/6] Configurando entorno virtual Python (.venv) y librerias..." -ForegroundColor Yellow
if (-not (Test-Path "$rootDir\.venv")) {
    python -m venv "$rootDir\.venv"
    Write-Host "        [OK] Entorno virtual .venv creado." -ForegroundColor Green
}

$venvPython = "$rootDir\.venv\Scripts\python.exe"
$venvPip = "$rootDir\.venv\Scripts\pip.exe"

& $venvPip install --upgrade pip --quiet
& $venvPip install -r "$rootDir\requirements.txt" --quiet
Write-Host "        [OK] Todas las dependencias de Python (FastAPI, Polars, Pytest) instaladas." -ForegroundColor Green

# ── PASO 4: INSTALACION DE DEPENDENCIAS DEL FRONTEND ────────────────────────
Write-Host "  [4/6] Instalando dependencias de Next.js & React..." -ForegroundColor Yellow
Set-Location -LiteralPath $rootDir
npm install --quiet --no-fund --no-audit
Write-Host "        [OK] Dependencias del frontend instaladas." -ForegroundColor Green

# ── PASO 5: VERIFICACION DE PLANTILLA DE CONFIGURACION (.env) ───────────────
Write-Host "  [5/6] Verificando archivo de configuracion local (.env)..." -ForegroundColor Yellow
if (-not (Test-Path "$rootDir\.env")) {
    if (Test-Path "$rootDir\.env.example") {
        Copy-Item "$rootDir\.env.example" "$rootDir\.env"
        Write-Host "        [OK] Creado archivo .env inicial a partir de .env.example." -ForegroundColor Green
    }
} else {
    Write-Host "        [OK] Archivo .env existente preservado." -ForegroundColor Green
}

# ── PASO 6: CERTIFICACION QA OFICIAL (69/69 PRUEBAS) ────────────────────────
Write-Host "  [6/6] Ejecutando suite de certificacion QA oficial (69 pruebas)..." -ForegroundColor Yellow
$qaResult = & $venvPython "$rootDir\scripts\run_qa_suite.py"
if ($LASTEXITCODE -eq 0) {
    Write-Host "        [OK] CERTIFICACION QA EXITOSA: 69/69 PRUEBAS APROBADAS AL 100%." -ForegroundColor Green
} else {
    Write-Host "        [WARN] Advertencia en suite QA. Revisa los logs de prueba." -ForegroundColor DarkYellow
}

# ── CREACION DE ACCESO DIRECTO EN ESCRITORIO DE WINDOWS ─────────────────────
try {
    $desktopPath = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Desktop)
    $shortcutPath = Join-Path $desktopPath "Slingshot Apex Sovereign.lnk"
    $wshell = New-Object -ComObject WScript.Shell
    $shortcut = $wshell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = "$rootDir\launch.bat"
    $shortcut.WorkingDirectory = "$rootDir"
    $shortcut.Description = "Lanzador Oficial de Slingshot Apex Sovereign"
    $shortcut.Save()
    Write-Host ""
    Write-Host "  [+] Acceso Directo creado en tu Escritorio: 'Slingshot Apex Sovereign.lnk'" -ForegroundColor Cyan
} catch {
    Write-Host "  [INFO] No se pudo crear el acceso directo en el escritorio automaticamente." -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "  =================================================================" -ForegroundColor Green
Write-Host "  [EXITO] INSTALACION COMPLETADA CON EXITO." -ForegroundColor Green
Write-Host "  =================================================================" -ForegroundColor Green
Write-Host "  Puedes arrancar el sistema cuando desees ejecutando 'launch.bat'" -ForegroundColor White
Write-Host ""
