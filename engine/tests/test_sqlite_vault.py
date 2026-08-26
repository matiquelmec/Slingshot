"""
engine/tests/test_sqlite_vault.py
=============================================================================
PRUEBAS UNITARIAS: BÓVEDA TRANSACCIONAL SQLITE WAL (VAULT v21.0)
=============================================================================
Valida:
1. Creación del esquema de base de datos con modo PRAGMA WAL.
2. Inserción atómica y deduplicación de alertas de Telegram.
3. Persistencia inmutable de sesiones y rotación de PDH/PDL.
4. Resistencia ante escrituras concurrentes (Thread-Safety).
"""
import pytest
import time
import threading
from pathlib import Path
from engine.core.vault import SlingshotVault

@pytest.fixture
def temp_vault(tmp_path):
    """Crea una instancia aislada de SlingshotVault en un directorio temporal."""
    test_db = tmp_path / "test_vault.db"
    v = SlingshotVault(db_path=test_db)
    return v

def test_vault_initialization_and_wal_mode(temp_vault):
    """Valida la creación correcta de tablas y la activación de WAL."""
    assert temp_vault.db_path.exists()
    
    with temp_vault._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode;")
        mode = cursor.fetchone()[0]
        assert mode.lower() == "wal", "El modo de diario debe ser WAL para alta concurrencia"

def test_telegram_dedup_and_cooldown(temp_vault):
    """Valida que is_signal_in_cooldown bloquee duplicados y permita nuevas alertas."""
    key = "BTCUSDT_LONG_15m"
    
    # 1. Al inicio no debe estar bloqueada
    is_blocked, _, _ = temp_vault.is_signal_in_cooldown(key, current_price=95000.0, cooldown_seconds=1800)
    assert is_blocked is False
    
    # 2. Registrar despacho
    temp_vault.record_signal_dispatch(key, "BTCUSDT", "LONG", "15m", 95000.0)
    
    # 3. Consulta inmediata al mismo precio -> Debe estar bloqueada
    is_blocked2, elapsed, pct_diff = temp_vault.is_signal_in_cooldown(key, current_price=95200.0, cooldown_seconds=1800)
    assert is_blocked2 is True
    assert elapsed < 5
    assert pct_diff < 1.0

def test_session_state_persistence(temp_vault):
    """Valida que los estados de sesión se guarden y recuperen fielmente."""
    state_payload = {
        "trading_day": "2026-08-26",
        "trades_today": 1,
        "asia": {"high": 96000.0, "low": 94000.0},
        "pdh": 96500.0,
        "pdl": 93800.0,
        "onh": 95800.0,
        "onl": 94200.0
    }
    
    temp_vault.save_session_state(
        symbol="BTCUSDT",
        trading_day="2026-08-26",
        pdh=96500.0,
        pdl=93800.0,
        onh=95800.0,
        onl=94200.0,
        state_dict=state_payload
    )
    
    loaded = temp_vault.load_session_state("BTCUSDT")
    assert loaded is not None
    assert loaded["trading_day"] == "2026-08-26"
    assert loaded["pdh"] == 96500.0
    assert loaded["asia"]["high"] == 96000.0

def test_concurrent_writes_thread_safety(temp_vault):
    """Valida la integridad de la base de datos bajo múltiples hilos concurrentes."""
    def worker(i):
        temp_vault.record_signal_dispatch(f"ASSET_{i}_LONG_15m", f"ASSET_{i}", "LONG", "15m", 100.0 + i)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    for t in threads: t.start()
    for t in threads: t.join()
    
    with temp_vault._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM telegram_dispatches;")
        count = cursor.fetchone()[0]
        assert count == 20, "Todos los 20 registros deben ser insertados sin colisiones ni locks"
