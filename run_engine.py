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

# Asegurar que stdout/stderr soporten UTF-8 incluso si el sistema intenta usar charmap (cp1252)
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

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
