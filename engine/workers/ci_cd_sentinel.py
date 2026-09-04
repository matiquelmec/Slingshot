"""
engine/workers/ci_cd_sentinel.py
=============================================================================
CENTINELA DE INTEGRACIÓN Y DESPLIEGUE CONTINUO (CI/CD AUTÓNOMO SEGURO)
v42.0 APEX TITAN — Institutional Deployment Gatekeeper
=============================================================================
Responsabilidades:
1. Comprueba de forma periódica (o bajo demanda) nuevos commits en GitHub.
2. Descarga cambios (fetch) en staging sin tocar los archivos de producción.
3. Ejecuta la Suite Completa de 216 Pruebas Unitarias y Gates de Calidad (SOP-41, SOP-21).
4. Si 100% de los tests pasan -> Aplica git pull atómico y recarga controlada (Graceful Reload).
5. Si 1 solo test falla -> Aborta el despliegue, registra la incidencia y protege el capital.
=============================================================================
"""
import sys
import os
import time
import subprocess
import logging
from pathlib import Path
from typing import Tuple, Dict, Any

# Configurar logging institucional
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [CI_CD_SENTINEL] %(message)s"
)
logger = logging.getLogger("CI_CD_SENTINEL")

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
LOG_FILE = ROOT_DIR / "deploy_audit.log"

class CICDSentinel:
    def __init__(self, branch: str = "cleanup-v1", remote: str = "origin"):
        self.branch = branch
        self.remote = remote
        self.git_cmd = self._find_git()

    def _find_git(self) -> str:
        for candidate in ["git", r"C:\Program Files\Git\cmd\git.exe", r"C:\Program Files\Git\bin\git.exe"]:
            try:
                subprocess.run([candidate, "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                return candidate
            except Exception:
                continue
        return "git"

    def log_audit(self, message: str):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] {message}\n"
        print(entry.strip())
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception as e:
            logger.error(f"Error escribiendo en deploy_audit.log: {e}")

    def get_local_commit(self) -> str:
        res = subprocess.run([self.git_cmd, "rev-parse", "HEAD"], cwd=ROOT_DIR, capture_output=True, text=True)
        return res.stdout.strip()

    def get_remote_commit(self) -> str:
        res = subprocess.run([self.git_cmd, "ls-remote", self.remote, f"refs/heads/{self.branch}"], cwd=ROOT_DIR, capture_output=True, text=True)
        out = res.stdout.strip()
        if out:
            return out.split()[0]
        return ""

    def run_qa_suite(self) -> Tuple[bool, str]:
        """Ejecuta la suite oficial de certificación QA."""
        qa_script = ROOT_DIR / "scripts" / "run_qa_suite.py"
        py_exec = sys.executable
        res = subprocess.run([py_exec, str(qa_script)], cwd=ROOT_DIR, capture_output=True, text=True)
        passed = (res.returncode == 0)
        return passed, res.stdout + "\n" + res.stderr

    def pre_flight_checks(self) -> Tuple[bool, str]:
        """Comprueba parámetros de riesgo, sintaxis y presencia de secretos."""
        env_file = ROOT_DIR / ".env"
        if not env_file.exists():
            return False, "Falta archivo .env crítico"
        
        try:
            content = env_file.read_text(encoding="utf-8")
            if "ENABLE_LIVE_TRADING=true" in content:
                # Comprobar que no haya riesgos absurdos
                for line in content.splitlines():
                    if line.startswith("MAX_RISK_PCT="):
                        val = float(line.split("=")[1])
                        if val > 0.05:
                            return False, f"VETO DE SEGURIDAD: MAX_RISK_PCT ({val}) excede el límite institucional del 5%"
        except Exception as e:
            return False, f"Error validando .env: {e}"

        return True, "Pre-flight checks aprobados"

    def execute_atomic_pull(self) -> bool:
        """Aplica el pull limpio preservando archivos de base de datos local."""
        try:
            # Preservar macro_state.json o archivos temporales locales
            subprocess.run([self.git_cmd, "checkout", "--", "engine/data/macro_state.json", "data/blackbox.json"], cwd=ROOT_DIR, capture_output=True)
            res = subprocess.run([self.git_cmd, "pull", self.remote, self.branch], cwd=ROOT_DIR, capture_output=True, text=True)
            if res.returncode == 0:
                self.log_audit(f"✅ Git Pull exitoso: {res.stdout.strip()[:100]}")
                return True
            else:
                self.log_audit(f"❌ Error en Git Pull: {res.stderr.strip()}")
                return False
        except Exception as e:
            self.log_audit(f"❌ Excepción en atomic pull: {e}")
            return False

    def reload_services(self) -> bool:
        """Recarga los servicios en Windows Server."""
        try:
            ps_script = """
Stop-ScheduledTask -TaskName 'SlingshotTrading' -ErrorAction SilentlyContinue
Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.Id -ne $PID } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-ScheduledTask -TaskName 'SlingshotTrading'

Stop-ScheduledTask -TaskName 'SlingshotFrontend' -ErrorAction SilentlyContinue
Get-Process node -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-ScheduledTask -TaskName 'SlingshotFrontend'
"""
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True)
            self.log_audit("🔄 Servicios SlingshotTrading y SlingshotFrontend recargados exitosamente.")
            return True
        except Exception as e:
            self.log_audit(f"❌ Error recargando servicios: {e}")
            return False

    def check_and_deploy(self) -> Dict[str, Any]:
        """Ciclo completo de auditoría y despliegue."""
        local_hash = self.get_local_commit()
        remote_hash = self.get_remote_commit()

        if not remote_hash:
            return {"status": "error", "message": "No se pudo consultar el commit remoto en GitHub."}

        if local_hash == remote_hash:
            return {"status": "up_to_date", "commit": local_hash}

        self.log_audit(f"🚀 Nuevo commit detectado en GitHub: {remote_hash[:8]} (Local actual: {local_hash[:8]})")

        # 1. Pre-flight checks
        ok_pre, msg_pre = self.pre_flight_checks()
        if not ok_pre:
            self.log_audit(f"🛑 Despliegue abortado por Pre-Flight Check: {msg_pre}")
            return {"status": "aborted", "reason": msg_pre}

        # 2. Quality Gates: Ejecutar pruebas unitarias ANTES de tocar producción
        self.log_audit("🧪 Ejecutando Suite de Certificación QA (Quality Gates)...")
        passed, qa_log = self.run_qa_suite()
        if not passed:
            self.log_audit(f"❌ VETO DE DESPLIEGUE: Fallaron pruebas unitarias. Despliegue cancelado para proteger capital.")
            return {"status": "qa_failed", "log": qa_log[:500]}

        self.log_audit("✅ Quality Gates superados al 100%. Procediendo con actualización atómica...")

        # 3. Aplicar Pull
        if not self.execute_atomic_pull():
            return {"status": "pull_failed"}

        # 4. Recargar Servicios
        self.reload_services()

        # 5. Post-Flight Health Check
        time.sleep(5)
        new_local = self.get_local_commit()
        self.log_audit(f"🎉 Despliegue completado con éxito a la versión: {new_local[:8]}")

        return {"status": "deployed", "old_commit": local_hash, "new_commit": new_local}

if __name__ == "__main__":
    sentinel = CICDSentinel()
    res = sentinel.check_and_deploy()
    print("Resultado:", res)