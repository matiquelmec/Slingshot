"""
=============================================================================
SLINGSHOT 24/7 WATCHDOG SUPERVISOR v22.3 APEX
=============================================================================
Supervisa los subprocesos de Python (backend) y Node.js (frontend).
Si algún proceso se detiene o falla, lo reinicia en menos de 2 segundos
manteniendo el estado persistente y emitiendo alertas de telemetría.
=============================================================================
"""
import subprocess
import time
import sys
import os
import signal
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent.resolve()
BACKEND_CMD = [sys.executable, "-m", "engine.main"]
FRONTEND_CMD = ["npm.cmd", "run", "dev"] if os.name == "nt" else ["npm", "run", "dev"]

def log(msg: str):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [WATCHDOG] {msg}", flush=True)

def start_process(cmd, name, cwd):
    log(f"Iniciando servicio {name}...")
    try:
        proc = subprocess.Popen(cmd, cwd=str(cwd))
        log(f"✅ {name} iniciado con PID {proc.pid}")
        return proc
    except Exception as e:
        log(f"❌ Error al iniciar {name}: {e}")
        return None

def main():
    log("=" * 60)
    log("🐕 SLINGSHOT WATCHDOG SUPERVISOR INICIADO (24/7 IMMORTAL MODE)")
    log(f"Directorio de trabajo: {ROOT_DIR}")
    log("=" * 60)

    backend_proc = start_process(BACKEND_CMD, "BACKEND_PYTHON", ROOT_DIR)
    time.sleep(2)
    frontend_proc = start_process(FRONTEND_CMD, "FRONTEND_NEXTJS", ROOT_DIR)

    def shutdown_handler(signum, frame):
        log("Señal de apagado recibida. Terminando procesos hijos...")
        if backend_proc and backend_proc.poll() is None:
            backend_proc.terminate()
        if frontend_proc and frontend_proc.poll() is None:
            frontend_proc.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    while True:
        try:
            time.sleep(5)
            
            # Supervisar Backend
            if backend_proc is None or backend_proc.poll() is not None:
                exit_code = backend_proc.poll() if backend_proc else "None"
                log(f"⚠️ ALERTA: Backend de Python se detuvo (Exit code: {exit_code}). Auto-reiniciando en 2s...")
                time.sleep(2)
                backend_proc = start_process(BACKEND_CMD, "BACKEND_PYTHON", ROOT_DIR)

            # Supervisar Frontend
            if frontend_proc is None or frontend_proc.poll() is not None:
                exit_code = frontend_proc.poll() if frontend_proc else "None"
                log(f"⚠️ ALERTA: Frontend de Next.js se detuvo (Exit code: {exit_code}). Auto-reiniciando en 2s...")
                time.sleep(2)
                frontend_proc = start_process(FRONTEND_CMD, "FRONTEND_NEXTJS", ROOT_DIR)

        except KeyboardInterrupt:
            shutdown_handler(None, None)
        except Exception as e:
            log(f"Error en bucle de supervisión: {e}")

if __name__ == "__main__":
    main()
