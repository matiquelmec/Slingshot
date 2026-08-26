"""
engine/tests/test_mt5_bridge.py
=============================================================================
PRUEBAS UNITARIAS: PUENTE DE EJECUCIÓN METATRADER 5 (MT5 BRIDGE v21.0)
=============================================================================
Valida:
1. Simulación Dry-Run de órdenes límite institucionales.
2. Cálculo exacto de lotes FTMO ($750 USD).
3. Bloqueo estricto de órdenes ante Kill-Switch de Drawdown Diario activado.
"""
import pytest
from engine.execution.mt5_bridge import MT5Bridge
from engine.risk.ftmo_guardian import ftmo_guardian

def test_mt5_bridge_dry_run_placement():
    """Valida la generación de parámetros de orden límite en modo Dry-Run."""
    bridge = MT5Bridge(dry_run=True)
    
    res = bridge.place_limit_order(
        symbol="XAUUSD",
        direction="LONG",
        entry_price=2350.0,
        stop_loss=2345.0, # $5 SL -> 1.5 Lotes
        tp1=2356.5,
        tp2=2361.0,
        tp3=2367.5,
        score=80
    )
    
    assert res["success"] is True
    assert res["mode"] == "DRY_RUN"
    assert res["symbol"] == "XAUUSD"
    assert res["order_type"] == "BUY_LIMIT"
    assert round(res["lots"], 2) == 1.50
    assert res["risk_usd"] == 750.0

def test_mt5_bridge_blocks_on_drawdown_lockout():
    """Valida que el puente rechace órdenes si FTMO Guardian está bloqueado."""
    bridge = MT5Bridge(dry_run=True)
    
    # Forzar lockout de seguridad
    ftmo_guardian.is_daily_lockout = True
    
    res = bridge.place_limit_order(
        symbol="US100",
        direction="SHORT",
        entry_price=18500.0,
        stop_loss=18550.0,
        tp1=18435.0,
        tp2=18390.0,
        tp3=18325.0
    )
    
    assert res["success"] is False
    assert res["reason"] == "FTMO_DAILY_DRAWDOWN_LOCKOUT"
    
    # Restaurar estado
    ftmo_guardian.is_daily_lockout = False
