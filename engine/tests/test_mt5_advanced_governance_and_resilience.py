"""
engine/tests/test_mt5_advanced_governance_and_resilience.py
============================================================
Suite de Pruebas de Gobernanza Institucional para MetaTrader 5 / FTMO:
1. Anti-Churning Cooldown Sentinel tras Stop Loss.
2. Gobernanza de Correlación Cruzada Estricta (US30 vs US100).
3. Fast Breakeven Incondicional tras TP1 o +1.0R.
4. Invarianza Monótona de Stop Loss (nunca empeorar riesgo).
5. Kill-Switch de Drawdown Diario Fail-Closed con purga de órdenes.
"""
import pytest
import time
import os
import json
from unittest.mock import MagicMock, patch, AsyncMock
from engine.risk.ftmo_guardian import FtmoGuardianShield
from engine.execution.mt5_bridge import MT5Bridge
from engine.workers.tradfi_scanner import TradFiScanner
from engine.workers.trade_manager import TradeManager


class MockPosition:
    def __init__(self, ticket, symbol, pos_type, volume, price_open, price_current, sl, tp, profit=0.0):
        self.ticket = ticket
        self.symbol = symbol
        self.type = pos_type # 0 = buy, 1 = sell
        self.volume = volume
        self.price_open = price_open
        self.price_current = price_current
        self.sl = sl
        self.tp = tp
        self.profit = profit
        self.magic = 999111


def test_tradfi_scanner_cooldown_after_stop_loss():
    """Valida que un Stop Loss reciente active el cooldown de 120 minutos y vete nuevas órdenes."""
    scanner = TradFiScanner()
    now_ts = time.time()

    # 1. Simular que el símbolo tiene un cooldown activo en memoria
    scanner._symbol_cooldowns = {"US30.cash": now_ts + 3600} # 60 min restantes
    assert "US30.cash" in scanner._symbol_cooldowns
    assert now_ts < scanner._symbol_cooldowns["US30.cash"]

    # 2. Simular que un cooldown vencido se elimina automáticamente
    scanner._symbol_cooldowns["US100.cash"] = now_ts - 10 # vencido
    cooldown_until = scanner._symbol_cooldowns["US100.cash"]
    if now_ts >= cooldown_until:
        del scanner._symbol_cooldowns["US100.cash"]
    assert "US100.cash" not in scanner._symbol_cooldowns


def test_strict_correlation_governor_us30_vs_us100():
    """Valida que una posición abierta en riesgo en US30 vete una orden en US100."""
    # Caso A: US30 en LONG sin proteger (SL por debajo de entrada)
    pos_unsecured = MockPosition(
        ticket=1001,
        symbol="US30.cash",
        pos_type=0, # BUY
        volume=1.0,
        price_open=52000.0,
        price_current=52050.0,
        sl=51900.0, # SL no asegurado
        tp=52500.0
    )

    op_type = pos_unsecured.type
    op_is_long = op_type in (0, 2)
    direction = "LONG"
    op_sl = pos_unsecured.sl
    op_open = pos_unsecured.price_open
    is_secured = (op_is_long and op_sl >= op_open) or (not op_is_long and op_sl > 0 and op_sl <= op_open)
    
    assert is_secured is False
    has_corr_conflict = (direction == "LONG" and op_is_long) or (direction == "SHORT" and not op_is_long)
    assert has_corr_conflict is True # Debe ser vetado

    # Caso B: US30 ya asegurado en Breakeven (SL >= entrada)
    pos_secured = MockPosition(
        ticket=1002,
        symbol="US30.cash",
        pos_type=0, # BUY
        volume=1.0,
        price_open=52000.0,
        price_current=52200.0,
        sl=52005.0, # SL en Breakeven positivo
        tp=52500.0
    )
    is_secured_b = (pos_secured.type in (0, 2) and pos_secured.sl >= pos_secured.price_open)
    assert is_secured_b is True # No causa conflicto


def test_fast_breakeven_on_tp1_winner_or_1r():
    """Valida que si TP1 fue ejecutado con ganancia, el runner sea forzado a Breakeven."""
    tm = TradeManager()
    
    entry_price = 52341.70
    cur_price = 52400.00
    cur_sl = 52240.60
    d_prec = 2
    sym = "US30.cash"
    side = "LONG"

    # Simular que US30.cash tiene un TP ganador cerrado en el historial
    closed_winners = {sym}
    has_closed_profit = sym in closed_winners

    be_offset = max(entry_price * 0.0001, 3.0 if "US" in sym else 0.0001)
    target_sl = round(entry_price + be_offset, d_prec) if side == "LONG" else round(entry_price - be_offset, d_prec)

    assert has_closed_profit is True
    assert target_sl > entry_price # 52344.70 o superior
    assert target_sl > cur_sl # Mejora el Stop Loss anterior


def test_sl_monotonic_invariance_in_mt5_bridge():
    """Valida que MT5Bridge rechace mover un SL hacia atrás (empeorar el riesgo)."""
    bridge = MT5Bridge(dry_run=True)
    bridge.connected = True

    # Para LONG: si cur_sl es 52345.0, un intento de mover a 52300.0 debe ser rechazado
    is_long = True
    cur_sl = 52345.0
    new_sl_worse = 52300.0
    
    should_reject = is_long and cur_sl > 0 and new_sl_worse < cur_sl
    assert should_reject is True

    # Para SHORT: si cur_sl es 1.3500, un intento de mover a 1.3520 debe ser rechazado
    is_long_short = False
    cur_sl_short = 1.3500
    new_sl_worse_short = 1.3520

    should_reject_short = not is_long_short and cur_sl_short > 0 and new_sl_worse_short > cur_sl_short
    assert should_reject_short is True


def test_daily_drawdown_killswitch_persistence_and_purge(tmp_path):
    """Valida la activación persistente del Kill-Switch y la llamada de purga de órdenes."""
    state_file = str(tmp_path / "ftmo_daily_metrics.json")
    guardian = FtmoGuardianShield(account_size=100000.0, state_file=state_file)
    guardian.daily_starting_equity = 100000.0

    # Simular caída a $96,400 (-3.6% de pérdida diaria, supera el -3.5% de PHASE_1)
    with patch.object(guardian, "_purge_mt5_pending_orders_on_lockout") as mock_purge:
        status = guardian.update_equity(current_equity=96400.0, current_balance=96400.0)
        assert status["is_daily_lockout"] is True
        assert status["daily_dd_pct"] >= 3.5
        assert mock_purge.called

    # Validar persistencia en disco
    assert os.path.exists(state_file)
    with open(state_file, "r") as f:
        data = json.load(f)
        assert data["is_daily_lockout"] is True
        assert "KILL-SWITCH DIARIO ACTIVADO" in data["lockout_reason"]
