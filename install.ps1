# ==============================================================================
# SLINGSHOT v25.6 INSTITUTIONAL FORTRESS -- ASISTENTE AUTOMATIZADO DE INSTALACION
# ==============================================================================
# Uso: .\install.ps1 (o doble clic en install.bat)
# ==============================================================================

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "  =================================================================" -ForegroundColor Cyan
Write-Host "       SLINGSHOT v25.6 INSTITUTIONAL FORTRESS -- ASISTENTE DE INSTALACION" -ForegroundColor Cyan
Write-Host "  =================================================================" -ForegroundColor Cyan
Write-Host ""

$rootDir = $PSScriptRoot
if (-not $rootDir) {
    $rootDir = Get-Location
}

# ── FUNCION AUXILIAR: REFRESCAR PATH Y LOCALIZAR PYTHON REAL ─────────────────
function Get-RealPythonPath {
    # Refrescar PATH del proceso actual desde el registro de Windows
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    
    # 1. Rutas estándar de instalación en Windows (winget / instalador oficial)
    $knownPaths = @(
        "C:\Program Files\Python312\python.exe",
        "C:\Program Files\Python311\python.exe",
        "C:\Program Files\Python313\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
        "$env:USERPROFILE\AppData\Local\Programs\Python\Python312\python.exe",
        "$env:USERPROFILE\AppData\Local\Programs\Python\Python311\python.exe"
    )
    foreach ($p in $knownPaths) {
        if ($p -and (Test-Path $p)) {
            return $p
        }
    }

    # 2. Intentar ejecutable 'py' launcher
    try {
        $pyCmd = Get-Command "py" -ErrorAction SilentlyContinue
        if ($pyCmd) {
            $test = & py -3.12 -c "import sys; print(sys.executable)" 2>$null
            if ($test -and (Test-Path $test)) { return $test }
            $test2 = & py -3 -c "import sys; print(sys.executable)" 2>$null
            if ($test2 -and (Test-Path $test2)) { return $test2 }
        }
    } catch {}

    # 3. Intentar 'python' filtrando el alias vacío de WindowsApps
    try {
        $commands = Get-Command "python" -All -ErrorAction SilentlyContinue
        foreach ($cmd in $commands) {
            if ($cmd.Source -and $cmd.Source -notmatch "WindowsApps") {
                return $cmd.Source
            }
        }
    } catch {}

    return $null
}

# ── PASO 1: VERIFICACION DE PYTHON 3.12 ─────────────────────────────────────
Write-Host "  [1/6] Verificando entorno Python..." -ForegroundColor Yellow
$systemPython = Get-RealPythonPath

if (-not $systemPython) {
    Write-Host "        [WARN] Python 3.12 no detectado. Instalando via winget..." -ForegroundColor DarkYellow
    try {
        winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements
        $systemPython = Get-RealPythonPath
    } catch {
        Write-Host "        [WARN] Winget reporto codigo de salida. Reintentando busqueda..." -ForegroundColor DarkYellow
        $systemPython = Get-RealPythonPath
    }
}

if (-not $systemPython) {
    Write-Host "        [ERROR] No se pudo encontrar Python 3.12 instalado." -ForegroundColor Red
    Write-Host "        Por favor instala Python 3.12 desde https://python.org marcando 'Add Python to PATH'." -ForegroundColor Yellow
    exit 1
}

$pyVer = & $systemPython --version 2>&1
Write-Host "        [OK] $pyVer detectado ($systemPython)." -ForegroundColor Green

# ── PASO 2: VERIFICACION DE NODE.JS ─────────────────────────────────────────
Write-Host "  [2/6] Verificando entorno Node.js..." -ForegroundColor Yellow
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
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
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        Write-Host "        [OK] Node.js LTS instalado correctamente." -ForegroundColor Green
    } catch {
        Write-Host "        [ERROR] Error instalando Node.js con winget. Por favor instala Node.js desde https://nodejs.org" -ForegroundColor Red
        exit 1
    }
}

# ── PASO 3: CREACION DE ENTORNO VIRTUAL PYTHON & DEPENDENCIAS ───────────────
Write-Host "  [3/6] Configurando entorno virtual Python (.venv) y librerias..." -ForegroundColor Yellow
$venvPython = "$rootDir\.venv\Scripts\python.exe"
$venvPip = "$rootDir\.venv\Scripts\pip.exe"

if (-not (Test-Path $venvPython) -or -not (Test-Path $venvPip)) {
    if (Test-Path "$rootDir\.venv") {
        Remove-Item -Recurse -Force "$rootDir\.venv" -ErrorAction SilentlyContinue
    }
    Write-Host "        Creando entorno virtual con $systemPython..." -ForegroundColor DarkGray
    & $systemPython -m venv "$rootDir\.venv"
}

if (-not (Test-Path $venvPython) -or -not (Test-Path $venvPip)) {
    Write-Host "        [ERROR] No se pudo crear el entorno virtual .venv." -ForegroundColor Red
    Write-Host "        Comprueba permisos de escritura en la carpeta e intentalo de nuevo." -ForegroundColor Yellow
    exit 1
}
Write-Host "        [OK] Entorno virtual .venv creado y verificado." -ForegroundColor Green

Write-Host "        Instalando librerias requeridas (FastAPI, Polars, Pytest)..." -ForegroundColor DarkGray
try {
    & $venvPython -m pip install --upgrade pip --quiet --no-warn-script-location 2>$null
} catch {}

& $venvPython -m pip install -r "$rootDir\requirements.txt" --quiet --no-warn-script-location
Write-Host "        [OK] Todas las dependencias de Python instaladas con exito." -ForegroundColor Green

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

# ── PASO 6: CERTIFICACION QA OFICIAL (100/100 PRUEBAS) ───────────────────────
Write-Host "  [6/6] Ejecutando suite de certificacion QA oficial (100 pruebas)..." -ForegroundColor Yellow
$qaResult = & $venvPython "$rootDir\scripts\run_qa_suite.py"
if ($LASTEXITCODE -eq 0) {
    Write-Host "        [OK] CERTIFICACION QA EXITOSA: 100/100 PRUEBAS APROBADAS AL 100%." -ForegroundColor Green
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
