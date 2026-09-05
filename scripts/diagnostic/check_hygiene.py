"""
scripts/diagnostic/check_hygiene.py
Validador de higiene de raíz del repositorio Slingshot.
"""
import sys
from pathlib import Path

ROOT_DIR = Path(r"C:\Slingshot")

def main():
    forbidden_prefixes = ("view_", "audit_", "check_", "patch_", "test_")
    forbidden_extensions = (".b64", ".tmp")
    violations = []

    for f in ROOT_DIR.iterdir():
        if f.is_file() and f.name != "pytest.ini":
            if any(f.name.startswith(p) for p in forbidden_prefixes):
                violations.append(f"Prefijo no permitido: {f.name}")
            elif any(f.name.endswith(e) for e in forbidden_extensions):
                violations.append(f"Extensión temporal: {f.name}")

    if violations:
        print("[ERROR] Se encontraron violaciones de higiene en raíz:")
        for v in violations:
            print(f"  - {v}")
        sys.exit(1)

    print("[OK] Raíz 100% limpia y estandarizada.")
    sys.exit(0)

if __name__ == "__main__":
    main()
