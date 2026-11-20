"""
scripts/diagnostic/check_hygiene.py
Validador de higiene institucional SSoT y OpSec (SOP-146) del repositorio Slingshot.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent

# Patrones OpSec prohibidos en archivos trackeados por Git (SOP-146)
FORBIDDEN_OPSEC_PATTERNS = [
    (re.compile(r"\b80\.65\.211\.99\b"), "IP pública del VPS expuesta en código/documentación"),
    (re.compile(r"auth\s*=\s*\(\s*['\"]Administrator['\"]\s*,\s*['\"][^'\"]+['\"]\s*\)"), "Credencial WinRM en texto plano detectada"),
]

SCAN_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".ps1", ".bat", ".md", ".json", ".env.example"}


def check_opsec_leaks() -> list[str]:
    """Escanea todos los archivos trackeados por Git en busca de fugas OpSec."""
    leaks: list[str] = []
    try:
        res = subprocess.run(
            ["git", "ls-files"],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            check=False,
        )
        tracked_files = [line.strip() for line in res.stdout.splitlines() if line.strip()]
    except Exception:
        tracked_files = []

    self_rel = Path(__file__).resolve().relative_to(ROOT_DIR).as_posix()
    for rel_path in tracked_files:
        norm_rel = rel_path.replace("\\", "/")
        if norm_rel == self_rel:
            continue
        fpath = ROOT_DIR / rel_path
        if not fpath.exists() or not fpath.is_file():
            continue
        if fpath.suffix.lower() not in SCAN_EXTENSIONS and fpath.name != ".env.example":
            continue
        try:
            content = fpath.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for regex, label in FORBIDDEN_OPSEC_PATTERNS:
            if regex.search(content):
                leaks.append(f"[OpSec SOP-146] {label} en: {norm_rel}")
    return leaks


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

    # 4. Escaneo OpSec Anti-Leak (SOP-146)
    violations.extend(check_opsec_leaks())

    if violations:
        print("[ERROR] Se encontraron violaciones de higiene institucional / OpSec:")
        for v in violations:
            print(f"  - {v}")
        sys.exit(1)

    print("[OK] Repositorio 100% limpio y certificado bajo estándar SSoT & OpSec SOP-146.")
    sys.exit(0)


if __name__ == "__main__":
    main()
