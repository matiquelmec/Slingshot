# Script de compilación GCC para la Inferencia GGUF SMC
# Misión "Ruptura de Barrera"
$engine_dir = "engine/inference"
gcc -shared -o $engine_dir/backbone_bridge.dll $engine_dir/backbone_bridge.c -O3 -Wall
Write-Host "✅ Módulos de Forja (backbone_bridge) recompilados para Slingshot v5.7.15" -ForegroundColor Green
