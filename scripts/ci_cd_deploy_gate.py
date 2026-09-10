"""
scripts/ci_cd_deploy_gate.py
=============================================================================
CLI para Ejecución Manual o Verificación del CI/CD Deployment Gate
=============================================================================
"""
import sys
from pathlib import Path

# Asegurar ROOT_DIR en sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from engine.workers.ci_cd_sentinel import CICDSentinel

def main():
    print("="*75)
    print("🛡️  SLINGSHOT v42.0 APEX TITAN — CI/CD DEPLOYMENT GATE")
    print("="*75)
    sentinel = CICDSentinel()
    
    local = sentinel.get_local_commit()
    remote = sentinel.get_remote_commit()
    print(f"Commit Local Actual : {local}")
    print(f"Commit Remoto GitHub : {remote}")
    
    if local == remote:
        print("\n✅ El sistema ya se encuentra en la versión más reciente.")
        sys.exit(0)
        
    print("\n🚀 Actualización pendiente detectada. Iniciando Quality Gate...")
    res = sentinel.check_and_deploy()
    print("\nResultado Final:", res)

if __name__ == "__main__":
    main()