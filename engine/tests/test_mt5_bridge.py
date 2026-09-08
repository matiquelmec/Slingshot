"""
engine/tests/test_mt5_bridge.py
=============================================================================
PRUEBAS UNITARIAS: PUENTE DE EJECUCIÓN METATRADER 5 (MT5 BRIDGE v22.3)
=============================================================================
Valida:
1. Simulación Dry-Run de órdenes límite institucionales.
2. Cálculo exacto de lotes FTMO ($750 USD).
3. Bloqueo estricto de órdenes ante Kill-Switch de Drawdown Diario activado.
4. División atómica en 3 salidas cuantitativas (50% TP1 / 30% TP2 / 20% TP3).
5. Interfaz de cancelación de órdenes pendientes.
6. Modificación segura de Take Profit (TP3).
7. Cierre parcial de posiciones abiertas (Partial Close DEAL).
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
        stop_loss=2345.0,  # $5 SL -> 1.5 Lotes
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


def test_mt5_bridge_three_split_exits():
    """Valida la división de órdenes en 3 tramos (50% / 30% / 20%)."""
    bridge = MT5Bridge(dry_run=True)
    res = bridge.place_limit_order(
        symbol='US100',
        direction='SHORT',
        entry_price=29582.0,
        stop_loss=29669.0,
        tp1=29468.0,
        tp2=29365.0,
        tp3=29210.0,
        score=95
    )
    assert res['success'] is True
    assert 'orders' in res
    assert len(res['orders']) == 3
    orders = res['orders']
    assert orders[0]['label'] == 'TP1_50pct'
    assert orders[1]['label'] == 'TP2_30pct'
    assert orders[2]['label'] == 'TP3_20pct'
    total_l = sum(o['lots'] for o in orders)
    assert round(total_l, 2) == round(res['total_lots'], 2)
    assert orders[0]['tp'] == 29468.0
    assert orders[1]['tp'] == 29365.0
    assert orders[2]['tp'] == 29210.0


def test_mt5_bridge_cancel_order_interface():
    """Valida la interfaz de cancelación de órdenes pendientes."""
    bridge = MT5Bridge(dry_run=True)
    assert bridge.cancel_order(123456) is True


def test_mt5_bridge_modify_position_tp():
    """Valida la modificación de TP sin alterar el SL."""
    bridge = MT5Bridge(dry_run=True)
    assert bridge.modify_position_tp(symbol="US100.cash", ticket=537417187, new_tp=29236.75) is True


def test_mt5_bridge_close_partial_position():
    """Valida la ejecución de cierre parcial en modo Dry-Run."""
    bridge = MT5Bridge(dry_run=True)
    assert bridge.close_partial_position(symbol="US100.cash", ticket=537417187, volume=4.30) is True
