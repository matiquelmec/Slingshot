"""
Slingshot Gen 1 - Engine Launcher
==================================
Ejecuta este script desde la raíz del proyecto para iniciar el backend FastAPI.

Uso:
    python run_engine.py
"""
import sys
import os

# Fuerza codificación UTF-8 en Windows para evitar crashes por emojis/símbolos
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"

# Asegurar que el directorio raíz del proyecto está en el path de Python
# para que todas las importaciones absolutas del paquete 'engine' funcionen.
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"[SLINGSHOT ENGINE] Iniciando en http://0.0.0.0:{port}")
    uvicorn.run(
        "engine.api.main:app",
        host="0.0.0.0",
        port=port,
        reload=False # Desactivar reload para mayor estabilidad
    )
