"""
scripts/ci_cd_deploy_gate.py
=============================================================================
CLI para Ejecución Manual o Verificación del CI/CD Deployment Gate
=============================================================================
"""
import sys
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