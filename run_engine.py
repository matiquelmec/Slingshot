"""
Slingshot Gen 1 - Engine Launcher
==================================
Ejecuta este script desde la raíz del proyecto para iniciar el backend FastAPI.

Uso:
    python run_engine.py
"""
import sys
import os

# Asegurar que el directorio raíz del proyecto está en el path de Python
# para que todas las importaciones absolutas del paquete 'engine' funcionen.
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import uvicorn

if __name__ == "__main__":
    print("[SLINGSHOT ENGINE] Iniciando en http://0.0.0.0:8000")
    uvicorn.run(
        "engine.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False # Desactivar reload para mayor estabilidad
    )
