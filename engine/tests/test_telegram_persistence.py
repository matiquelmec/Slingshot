"""
engine/tests/test_telegram_persistence.py
=============================================================================
PRUEBAS UNITARIAS: PERSISTENCIA EN DISCO, ANTI-SPAM Y THROTTLE DE TELEGRAM
=============================================================================
Valida:
1. Persistencia de estado en SQLite Vault (slingshot_vault.db).
2. Sobrevivencia a reinicios: Una nueva instancia recuerda las señales enviadas y bloquea duplicados.
3. Permitir re-disparo legítimo si el precio tiene una variación >= 3% o tras 30 min.
4. Purga automática de registros antiguos.
"""
import pytest
import time
from engine.router.telegram_dispatcher import TelegramDispatcher
from engine.core.vault import vault

@pytest.mark.asyncio
async def test_reboot_survival_no_duplicate_signal():
    """
    TEST CRÍTICO: Valida que si el sistema se apaga y se vuelve a encender,
    NO vuelve a enviar la misma señal si está dentro del cooldown y precio similar.
    """
    # 1. Instancia 1 registra señal en SQLite
    vault.record_signal_dispatch(
        dedup_key="SOLUSDT_LONG_15m",
        asset="SOLUSDT",
        direction="LONG",
        timeframe="15m",
        price=180.0
    )
    
    # 2. Simular REINICIO del bot (D2 nace desde cero)
    d2 = TelegramDispatcher(cooldown_seconds=1800)
    d2.enabled = True
    
    signal = {
        "asset": "SOLUSDT",
        "direction": "LONG",
        "signal_type": "LONG",
        "price": 180.0,
        "stop_loss": 175.0,
        "confluence_score": 75,
        "timeframe": "15m"
    }
    
    # Evaluar si la señal duplicada pasa
    # Precio igual (180.0) dentro de 30 min -> Debe ser bloqueada (retorna False)
    result = await d2.send_signal_alert(signal)
    assert result is False, "La señal idéntica debe ser bloqueada tras el reinicio gracias a SQLite Vault"

def test_price_drift_allows_retrigger():
    """Valida que si el precio varía >= 3.0% (nueva estructura), se permita la alerta."""
    key = "ETHUSDT_LONG_15m"
    vault.record_signal_dispatch(key, "ETHUSDT", "LONG", "15m", 3000.0)
    
    # Caso 1: Precio 3005 (+0.16% de variación) -> Bloqueado
    is_blocked, _, _ = vault.is_signal_in_cooldown(key, current_price=3005.0, cooldown_seconds=1800, max_drift_pct=3.0)
    assert is_blocked is True
    
    # Caso 2: Precio 3100 (+3.33% de variación) -> Permitido
    is_blocked2, _, pct_diff = vault.is_signal_in_cooldown(key, current_price=3100.0, cooldown_seconds=1800, max_drift_pct=3.0)
    assert is_blocked2 is False
    assert pct_diff >= 3.0

def test_purge_old_dispatches():
    """Valida que la purga de registros antiguos mantenga la base de datos optimizada."""
    vault.purge_old_dispatches(retention_hours=24)
