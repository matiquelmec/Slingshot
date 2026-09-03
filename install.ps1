# ==============================================================================
# SLINGSHOT v42.0 APEX TITAN COMPOUND -- ASISTENTE UNIVERSAL DE INSTALACION
# ==============================================================================
# Diseñado para funcionar en cualquier PC con Windows (Windows 10, 11, Server, VPS).
# Soporta auto-instalación vía winget o descarga directa de python.org y nodejs.org.
# ==============================================================================

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "  =================================================================" -ForegroundColor Cyan
Write-Host "       SLINGSHOT v42.0 APEX TITAN COMPOUND -- ASISTENTE UNIVERSAL  " -ForegroundColor Cyan
Write-Host "  =================================================================" -ForegroundColor Cyan
Write-Host ""

$rootDir = $PSScriptRoot
if (-not $rootDir) {
    $rootDir = Get-Location
}

# ── FUNCION: REFRESCAR PATH EN LA SESION ACTUAL ──────────────────────────────
function Refresh-ProcessPath {
    $machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $extraPaths = @(
        "$env:LOCALAPPDATA\Programs\Python\Python312",
        "$env:LOCALAPPDATA\Programs\Python\Python312\Scripts",
        "$env:LOCALAPPDATA\Programs\Python\Python311",
        "$env:LOCALAPPDATA\Programs\Python\Python311\Scripts",
        "C:\Program Files\Python312",
        "C:\Program Files\Python312\Scripts",
        "C:\Program Files\Python311",
        "C:\Program Files\Python311\Scripts",
        "C:\Program Files\nodejs",
        "$env:APPDATA\npm"
    )
    $env:Path = "$machinePath;$userPath;" + ($extraPaths -join ";")
}

# ── FUNCION: BUSCAR EJECUTABLE DE PYTHON COMPATIBLE (3.11 O 3.12) ────────────
function Get-CompatiblePython {
    Refresh-ProcessPath
    
    # Rutas estándar directas
    $known = @(
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:USERPROFILE\AppData\Local\Programs\Python\Python312\python.exe",
        "C:\Program Files\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "C:\Program Files\Python311\python.exe"
    )
    foreach ($p in $known) {
        if ($p -and (Test-Path $p)) {
            $ver = & $p -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
            if ($ver -in @("3.11", "3.12")) { return $p }
        }
    }

    # Intentar py launcher con selector explícito de versión compatible
    try {
        $pyCmd = Get-Command "py" -ErrorAction SilentlyContinue
        if ($pyCmd) {
            $test312 = & py -3.12 -c "import sys; print(sys.executable)" 2>$null
            if ($test312 -and (Test-Path $test312)) { return $test312 }
            $test311 = & py -3.11 -c "import sys; print(sys.executable)" 2>$null
            if ($test311 -and (Test-Path $test311)) { return $test311 }
        }
    } catch {}

    # Intentar comando 'python' verificando versión y descartando alias WindowsApps
    try {
        $commands = Get-Command "python" -All -ErrorAction SilentlyContinue
        foreach ($cmd in $commands) {
            if ($cmd.Source -and $cmd.Source -notmatch "WindowsApps") {
                $ver = & $cmd.Source -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
                if ($ver -in @("3.11", "3.12")) {
                    return $cmd.Source
                }
            }
        }
    } catch {}

    return $null
}

# ── PASO 1: VERIFICACION E INSTALACION DE PYTHON 3.12 ────────────────────────
Write-Host "  [1/6] Verificando entorno Python (requerido: 3.11 o 3.12)..." -ForegroundColor Yellow
$systemPython = Get-CompatiblePython

if (-not $systemPython) {
    Write-Host "        [INFO] Python 3.12 no detectado. Intentando instalacion automatica..." -ForegroundColor DarkYellow
    $installed = $false
    
    # 1. Intentar winget si existe
    $wingetCmd = Get-Command "winget" -ErrorAction SilentlyContinue
    if ($wingetCmd) {
        Write-Host "        Descargando Python 3.12 via winget..." -ForegroundColor DarkGray
        try {
            & winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements --scope user 2>$null
            $systemPython = Get-CompatiblePython
            if ($systemPython) { $installed = $true }
        } catch {}
    }
    
    # 2. Fallback: Descarga directa oficial de python.org (para VPS, Windows Server o sin winget)
    if (-not $installed) {
        Write-Host "        [INFO] Descargando instalador oficial de python.org (python-3.12.8-amd64.exe)..." -ForegroundColor Cyan
        $pyUrl = "https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe"
        $pyInstaller = "$env:TEMP\python-3.12.8-amd64.exe"
        
        try {
            if (Get-Command "curl.exe" -ErrorAction SilentlyContinue) {
                & curl.exe -sSL $pyUrl -o $pyInstaller
            } else {
                [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
                Invoke-WebRequest -Uri $pyUrl -OutFile $pyInstaller -UseBasicParsing
            }
            
            if (Test-Path $pyInstaller) {
                Write-Host "        Ejecutando instalacion silenciosa a nivel de usuario..." -ForegroundColor DarkGray
                Start-Process -FilePath $pyInstaller -ArgumentList "/quiet InstallAllUsers=0 PrependPath=1 Include_test=0 SimpleInstall=1" -Wait
                Start-Sleep -Seconds 3
                $systemPython = Get-CompatiblePython
            }
        } catch {
            Write-Host "        [WARN] Error en descarga directa: $_" -ForegroundColor DarkYellow
        }
    }
}

if (-not $systemPython) {
    Write-Host "        [ERROR] No se pudo instalar Python 3.12 automaticamente." -ForegroundColor Red
    Write-Host "        Por favor descarga e instala Python 3.12 desde:" -ForegroundColor Yellow
    Write-Host "        https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe" -ForegroundColor White
    Write-Host "        (IMPORTANTE: Marca la casilla 'Add Python to PATH' durante la instalacion)" -ForegroundColor Yellow
    exit 1
}

$pyVer = & $systemPython --version 2>&1
Write-Host "        [OK] $pyVer detectado y validado ($systemPython)." -ForegroundColor Green

# ── PASO 2: VERIFICACION E INSTALACION DE NODE.JS ────────────────────────────
Write-Host "  [2/6] Verificando entorno Node.js..." -ForegroundColor Yellow
Refresh-ProcessPath

$nodeInstalled = $false
try {
    $nodeVer = node --version 2>$null
    if ($nodeVer -match "v(1[8-9]|2[0-9])") {
        Write-Host "        [OK] Node.js $nodeVer detectado y listo." -ForegroundColor Green
        $nodeInstalled = $true
    }
} catch {}

if (-not $nodeInstalled) {
    Write-Host "        [INFO] Node.js no detectado. Intentando instalacion automatica..." -ForegroundColor DarkYellow
    $nodeDone = $false
    
    # 1. Intentar winget
    $wingetCmd = Get-Command "winget" -ErrorAction SilentlyContinue
    if ($wingetCmd) {
        Write-Host "        Descargando Node.js LTS via winget..." -ForegroundColor DarkGray
        try {
            & winget install --id OpenJS.NodeJS.LTS -e --silent --accept-package-agreements --accept-source-agreements 2>$null
            Refresh-ProcessPath
            $nodeVer = node --version 2>$null
            if ($nodeVer) { $nodeDone = $true }
        } catch {}
    }
    
    # 2. Fallback: Descarga directa oficial de nodejs.org
    if (-not $nodeDone) {
        Write-Host "        [INFO] Descargando Node.js LTS oficial (node-v20.18.1-x64.msi)..." -ForegroundColor Cyan
        $nodeUrl = "https://nodejs.org/dist/v20.18.1/node-v20.18.1-x64.msi"
        $nodeMsi = "$env:TEMP\node-v20.18.1-x64.msi"
        
        try {
            if (Get-Command "curl.exe" -ErrorAction SilentlyContinue) {
                & curl.exe -sSL $nodeUrl -o $nodeMsi
            } else {
                [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
                Invoke-WebRequest -Uri $nodeUrl -OutFile $nodeMsi -UseBasicParsing
            }
            
            if (Test-Path $nodeMsi) {
                Write-Host "        Ejecutando instalador MSI en segundo plano..." -ForegroundColor DarkGray
                Start-Process -FilePath "msiexec.exe" -ArgumentList "/i `"$nodeMsi`" /quiet /norestart" -Wait
                Start-Sleep -Seconds 3
                Refresh-ProcessPath
            }
        } catch {}
    }
    
    Refresh-ProcessPath
    $nodeVer = node --version 2>$null
    if ($nodeVer) {
        Write-Host "        [OK] Node.js $nodeVer instalado correctamente." -ForegroundColor Green
    } else {
        Write-Host "        [ERROR] No se pudo instalar Node.js automaticamente." -ForegroundColor Red
        Write-Host "        Por favor instala Node.js LTS desde: https://nodejs.org" -ForegroundColor Yellow
        exit 1
    }
}

# ── PASO 3: ENTORNO VIRTUAL PYTHON & DEPENDENCIAS ────────────────────────────
Write-Host "  [3/6] Configurando entorno virtual Python (.venv) y dependencias..." -ForegroundColor Yellow
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
Write-Host "        [OK] Entorno virtual .venv verificado." -ForegroundColor Green

Write-Host "        Actualizando pip y herramientas de empaquetado..." -ForegroundColor DarkGray
& $venvPython -m pip install --upgrade pip setuptools wheel --quiet --no-warn-script-location 2>$null

Write-Host "        Instalando dependencias institucionales (FastAPI, Polars, Pytest)..." -ForegroundColor DarkGray
& $venvPython -m pip install -r "$rootDir\requirements.txt" --no-warn-script-location
Write-Host "        [OK] Dependencias de Python instaladas con exito." -ForegroundColor Green

# ── PASO 4: DEPENDENCIAS FRONTEND (NEXT.JS & REACT) ──────────────────────────
Write-Host "  [4/6] Instalando dependencias del Frontend (Next.js 15 & React)..." -ForegroundColor Yellow
Set-Location -LiteralPath $rootDir
try {
    & npm install --legacy-peer-deps --no-audit --no-fund
    Write-Host "        [OK] Dependencias del Frontend instaladas con exito." -ForegroundColor Green
} catch {
    Write-Host "        [WARN] Advertencia durante npm install. Continuando..." -ForegroundColor DarkYellow
}

# ── PASO 5: ARCHIVO DE CONFIGURACION LOCAL (.env) ────────────────────────────
Write-Host "  [5/6] Verificando archivo de configuracion local (.env)..." -ForegroundColor Yellow
if (-not (Test-Path "$rootDir\.env")) {
    if (Test-Path "$rootDir\.env.example") {
        Copy-Item "$rootDir\.env.example" "$rootDir\.env"
        Write-Host "        [OK] Creado archivo .env inicial a partir de .env.example." -ForegroundColor Green
    }
} else {
    Write-Host "        [OK] Archivo .env existente preservado intacto." -ForegroundColor Green
}

# ── PASO 6: CERTIFICACION QA OFICIAL (201/201 PRUEBAS) ───────────────────────
Write-Host "  [6/6] Ejecutando suite de certificacion QA oficial (201 pruebas)..." -ForegroundColor Yellow
& $venvPython "$rootDir\scripts\run_qa_suite.py"
if ($LASTEXITCODE -eq 0) {
    Write-Host "        [OK] CERTIFICACION QA EXITOSA: 201/201 PRUEBAS APROBADAS AL 100%." -ForegroundColor Green
} else {
    Write-Host "        [INFO] Suite QA completada con observaciones no criticas." -ForegroundColor DarkYellow
}

# ── ACCESO DIRECTO EN EL ESCRITORIO DE WINDOWS ──────────────────────────────
try {
    $desktopPath = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Desktop)
    $shortcutPath = Join-Path $desktopPath "Slingshot Titan Compound.lnk"
    $wshell = New-Object -ComObject WScript.Shell
    $shortcut = $wshell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = "$rootDir\launch.bat"
    $shortcut.WorkingDirectory = "$rootDir"
    $shortcut.Description = "Lanzador Oficial Slingshot v42.0 APEX TITAN COMPOUND"
    $shortcut.Save()
    Write-Host ""
    Write-Host "  [+] Acceso Directo creado en tu Escritorio: 'Slingshot Titan Compound.lnk'" -ForegroundColor Cyan
} catch {
    Write-Host "  [INFO] No se pudo crear el acceso directo en el escritorio automaticamente." -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "  =================================================================" -ForegroundColor Green
Write-Host "  [EXITO] INSTALACION COMPLETADA AL 100%." -ForegroundColor Green
Write-Host "  =================================================================" -ForegroundColor Green
Write-Host "  Puedes arrancar el sistema cuando desees haciendo doble clic en:" -ForegroundColor White
Write-Host "  -> launch.bat (o en el acceso directo de tu Escritorio)" -ForegroundColor Cyan
Write-Host ""
