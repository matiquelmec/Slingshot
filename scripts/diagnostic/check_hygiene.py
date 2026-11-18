"""
scripts/diagnostic/check_hygiene.py
Validador de higiene institucional SSoT del repositorio Slingshot.
"""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent

def main():
    forbidden_prefixes = ("view_", "audit_", "check_", "patch_", "test_")
    forbidden_extensions = (".b64", ".tmp")
    blacklisted_session_assets = ("PAXGUSDT", "XAGUSDT", "XRPUSDT")
    violations = []

    # 1. Higiene de Raíz
    for f in ROOT_DIR.iterdir():
        if f.is_file() and f.name != "pytest.ini":
            if any(f.name.startswith(p) for p in forbidden_prefixes):
                violations.append(f"Prefijo no permitido en raíz: {f.name}")
            elif any(f.name.endswith(e) for e in forbidden_extensions):
                violations.append(f"Extensión temporal en raíz: {f.name}")

    # 2. Higiene SSoT en docs/ y scripts/ (Sin archivos obsoletos ni carpetas vacías)
    docs_dir = ROOT_DIR / "docs"
    if docs_dir.exists():
        bibles = [f.name for f in docs_dir.glob("SLINGSHOT_BIBLE_*.md")]
        if bibles:
            violations.append(f"Biblias heredadas fuera de estándar BLUEPRINT_2026.md: {bibles}")
        if (docs_dir / "archive").exists():
            violations.append("Directorio obsoleto docs/archive/ detectado.")

    for obsolete_dir in (ROOT_DIR / "scratch", ROOT_DIR / "scripts" / "archive"):
        if obsolete_dir.exists():
            violations.append(f"Directorio obsoleto detectado: {obsolete_dir.relative_to(ROOT_DIR)}")

    # 3. Higiene de Estado en engine/data/ (Sin activos erradicados)
    engine_data_dir = ROOT_DIR / "engine" / "data"
    if engine_data_dir.exists():
        for asset in blacklisted_session_assets:
            orphan_file = engine_data_dir / f"session_state_{asset}.json"
            if orphan_file.exists():
                violations.append(f"Estado huérfano de activo erradicado en engine/data/: {orphan_file.name}")

    if violations:
        print("[ERROR] Se encontraron violaciones de higiene institucional:")
        for v in violations:
            print(f"  - {v}")
        sys.exit(1)

    print("[OK] Repositorio 100% limpio y certificado bajo estándar SSoT v60.0.")
    sys.exit(0)

if __name__ == "__main__":
    main()

