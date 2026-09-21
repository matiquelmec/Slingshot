import pytest
import asyncio
import pandas as pd
from engine.risk.risk_manager import RiskManager
from engine.workers.trade_manager import TradeManager
from engine.indicators.htf_analyzer import HTFBias

class MockExecutor:
    def __init__(self, account_label="mock_primary"):
        self.account_label = account_label
        self.modified_positions = []

    async def modify_position_tpsl(self, symbol: str, position_id: str = None, sl_price: float = None, tp_price: float = None):
        self.modified_positions.append({"symbol": symbol, "sl": sl_price})
        return True

@pytest.fixture
def risk_manager():
    return RiskManager(account_balance=1000.0, base_risk_pct=0.02)

@pytest.fixture
def trade_manager():
    return TradeManager()

def test_regime_runner_mode_selection(risk_manager):
    # Test 1: Expansion regime (MARKUP) with BULLISH bias -> OPEN_RUNNER (50/30/10/10)
    htf_bias_bull = HTFBias(
        direction="BULLISH", strength=0.85, reason="Test Bull",
        m1_regime="MARKUP", w1_regime="MARKUP", d1_regime="MARKUP", h4_regime="MARKUP", h1_regime="MARKUP"
    )
    res_runner = risk_manager.calculate_position(
        current_price=50000.0,
        signal_type="LONG",
        atr_value=500.0,
        asset="BTCUSDT",
        market_regime="MARKUP",
        htf_bias=htf_bias_bull,
        confluence_score=78
    )
    assert res_runner["runner_mode"] == "OPEN_RUNNER"
    assert res_runner["tp1_pct"] == 0.50
    assert res_runner["tp2_pct"] == 0.30
    assert res_runner["tp3_pct"] == 0.10
    assert res_runner["runner_pct"] == 0.10

    # Test 2: Ranging regime -> FIXED_TARGET (50/30/20)
    res_fixed = risk_manager.calculate_position(
        current_price=50000.0,
        signal_type="LONG",
        atr_value=500.0,
        asset="BTCUSDT",
        market_regime="RANGING",
        htf_bias=htf_bias_bull,
        confluence_score=70
    )
    assert res_fixed["runner_mode"] == "FIXED_TARGET"
    assert res_fixed["tp1_pct"] == 0.50
    assert res_fixed["tp2_pct"] == 0.30
    assert res_fixed["tp3_pct"] == 0.20
    assert res_fixed["runner_pct"] == 0.00

def test_monotonic_sl_invariance(trade_manager):
    # Long SL must only increase
    assert trade_manager._sl_improved(old_sl=49000.0, new_sl=49500.0, is_long=True) is True
    assert trade_manager._sl_improved(old_sl=49500.0, new_sl=49000.0, is_long=True) is False

    # Short SL must only decrease
    assert trade_manager._sl_improved(old_sl=51000.0, new_sl=50500.0, is_long=False) is True
    assert trade_manager._sl_improved(old_sl=50500.0, new_sl=51000.0, is_long=False) is False

@pytest.mark.asyncio
async def test_trade_manager_phase_transition_fixed_vs_runner(trade_manager, monkeypatch):
    # Mock _apply_sl_update to track updates
    updates = []
    async def mock_apply(signal, new_sl, new_phase, reason):
        updates.append({"phase": new_phase, "sl": new_sl, "reason": reason})
        signal["trailing_phase"] = new_phase
        signal["stop_loss"] = new_sl

    monkeypatch.setattr(trade_manager, "_apply_sl_update", mock_apply)

    # 1. FIXED_TARGET trade reaching TP3 -> Should transition to CLOSED
    signal_fixed = {
        "asset": "BTCUSDT",
        "signal_type": "LONG",
        "price": 50000.0,
        "stop_loss": 51000.0,
        "tp1": 50700.0,
        "tp2": 51200.0,
        "tp3": 52000.0,
        "trailing_phase": "TRAILING",
        "runner_mode": "FIXED_TARGET"
    }
    
    # Mock fetch_binance_history returning price >= tp3
    async def mock_fetch(asset, interval, limit):
        return [{"data": {"timestamp": 1000 + i*60, "open": 52100.0, "high": 52200.0, "low": 52050.0, "close": 52100.0, "volume": 100, "atr": 200.0}} for i in range(limit)]

    monkeypatch.setattr("engine.workers.trade_manager.fetch_binance_history", mock_fetch)

    await trade_manager._update_signal_trailing(signal_fixed)
    assert len(updates) == 1
    assert updates[0]["phase"] == "CLOSED"

    # 2. OPEN_RUNNER trade reaching TP3 -> Should transition to RUNNER_EXPANSION (NOT CLOSED!)
    updates.clear()
    signal_runner = {
        "asset": "BTCUSDT",
        "signal_type": "LONG",
        "price": 50000.0,
        "stop_loss": 51000.0,
        "tp1": 50700.0,
        "tp2": 51200.0,
        "tp3": 52000.0,
        "trailing_phase": "TRAILING",
        "runner_mode": "OPEN_RUNNER"
    }

    await trade_manager._update_signal_trailing(signal_runner)
    assert len(updates) == 1
    assert updates[0]["phase"] == "RUNNER_EXPANSION"
    assert signal_runner["trailing_phase"] == "RUNNER_EXPANSION"
    assert updates[0]["sl"] >= 51200.0 # Blindado al menos a TP2
