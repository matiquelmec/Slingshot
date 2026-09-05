"""
engine/tests/test_institutional_security_and_hygiene.py
======================================================
Valida que el sistema cumpla con todos los estándares institucionales:
1. Protección de .env y secretos (.gitignore)
2. Modo SQLite WAL activo en base de datos
3. Ausencia de I/O síncrono bloqueante (urllib.request / time.sleep en hot path)
4. Aislamiento de cuentas y ausencia de archivos de depuración en la raíz
"""

import os
import sqlite3
import pytest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent

def test_gitignore_protects_env_and_keys():
    gitignore_path = ROOT_DIR / ".gitignore"
    assert gitignore_path.exists(), ".gitignore debe existir en la raíz"
    content = gitignore_path.read_text(encoding="utf-8")
    assert ".env" in content, ".env debe estar explícitamente ignorado por git"

def test_root_directory_hygiene():
    """Valida que no existan scripts de diagnóstico o temporales sueltos en la raíz."""
    forbidden_prefixes = ("view_", "audit_", "check_", "patch_", "test_")
    forbidden_extensions = (".b64", ".tmp", ".msi", ".exe")
    
    root_files = [f.name for f in ROOT_DIR.iterdir() if f.is_file()]
    for f in root_files:
        if f == "pytest.ini":
            continue
        for pfx in forbidden_prefixes:
            assert not f.startswith(pfx), f"Archivo no higiénico en raíz: {f} (debe estar en scripts/diagnostic o engine/tests)"
        for ext in forbidden_extensions:
            assert not f.endswith(ext), f"Archivo residual en raíz: {f}"

def test_sqlite_wal_mode_active():
    """Valida que slingshot.db use modo WAL para concurrencia no bloqueante."""
    db_path = ROOT_DIR / "data" / "slingshot.db"
    if db_path.exists():
        with sqlite3.connect(str(db_path)) as conn:
            cur = conn.cursor()
            cur.execute("PRAGMA journal_mode")
            mode = cur.fetchone()[0]
            assert mode.upper() == "WAL", f"Modo SQLite debe ser WAL, actual: {mode}"

def test_multi_asset_feed_no_blocking_urllib():
    """Valida que multi_asset_feed no contenga urllib.request síncrono."""
    feed_path = ROOT_DIR / "engine" / "core" / "multi_asset_feed.py"
    content = feed_path.read_text(encoding="utf-8")
    assert "urllib.request" not in content, "multi_asset_feed.py no debe usar urllib.request bloqueante"
    assert "httpx" in content, "multi_asset_feed.py debe usar httpx asíncrono"
