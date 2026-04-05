# 🏹 Forja de Silicio Nativo: Slingshot Inferencia GGUF (v5.5-Forge)
# Ejecuta este script desde una terminal de PowerShell para compilar el Bridge C++.

$ErrorActionPreference = "Stop"

$BRIDGE_SRC = "c:\Users\Matías Riquelme\Desktop\Proyectos documentados\Slingshot_Trading\engine\inference\backbone_bridge.c"
$DLL_OUT = "c:\Users\Matías Riquelme\Desktop\Proyectos documentados\Slingshot_Trading\engine\inference\libbackbone_bridge.dll"

# OMEGA: Detección de Prerrequisitos
Write-Host "🔍 Detectando entorno de compilación..." -ForegroundColor Cyan

$has_gcc = Get-Command gcc -ErrorAction SilentlyContinue
$has_cl = Get-Command cl -ErrorAction SilentlyContinue

if ($has_gcc) {
    Write-Host "✅ MinGW (gcc) detectado. Iniciando forja nativa..." -ForegroundColor Green
    # Nota: Requiere llama.h en el path de inclusión
    & gcc -shared -fPIC -O3 -o $DLL_OUT $BRIDGE_SRC `
        -I"c:\Users\Matías Riquelme\Desktop\MOSS-TTS-main\moss_tts_delay\llama_cpp\llama.cpp\include" `
        -L"c:\Users\Matías Riquelme\Desktop\MOSS-TTS-main\moss_tts_delay\llama_cpp\llama.cpp\build\bin" `
        -lllama
} 
elseif ($has_cl) {
    Write-Host "✅ MSVC (cl) detectado. Iniciando forja industrial..." -ForegroundColor Green
    & cl /LD /O2 /Fe:$DLL_OUT $BRIDGE_SRC `
        /I"c:\Users\Matías Riquelme\Desktop\MOSS-TTS-main\moss_tts_delay\llama_cpp\llama.cpp\include" `
        "c:\Users\Matías Riquelme\Desktop\MOSS-TTS-main\moss_tts_delay\llama_cpp\llama.cpp\build\bin\llama.lib"
}
else {
    Write-Host "❌ No se encontró un compilador compatible (gcc/cl) en el PATH." -ForegroundColor Red
    Write-Host "💡 Sugerencia OMEGA: Instala MinGW-w64 o Visual Studio Build Tools." -ForegroundColor Yellow
    Write-Host "👉 Alternativa: Puedes usar el bridge pre-compilado de MOSS si es compatible." -ForegroundColor Gray
}

if (Test-Path $DLL_OUT) {
    Write-Host "🔥 Forja Completada: $DLL_OUT generado con éxito." -ForegroundColor Green
    Write-Host "🚀 Slingshot v5.5 ahora tiene acceso directo al silicio." -ForegroundColor Cyan
}
else {
    Write-Host "⚠️ Error en la forja. Revisa las dependencias de llama.cpp." -ForegroundColor Yellow
}
