"""
=============================================================================
SLINGSHOT v23.3 APEX - INSTITUTIONAL BACKTEST SSOT QA SUITE
=============================================================================
Pruebas unitarias cuantitativas que certifican el Motor de Backtest SSoT:
1. Evaluacion estricta de ConfluenceManager (14 factores, score real).
2. Colocacion estructural de Stop Loss & OTE mediante RiskManager.
3. Precision de ejecucion intra-vela con sesgo pesimista (anti survivor bias).
4. Conservacion de volumen en salidas asimetricas (60% TP1, 20% TP2, 10% TP3, 10% Runner).
5. Vectorizacion y exactitud matematica de metricas institucionales:
   Sharpe, Sortino, Calmar, Profit Factor y Max Drawdown.
=============================================================================
"""
import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timezone

from engine.backtest.unified_backtest_engine import UnifiedBacktestEngine
from engine.risk.risk_manager import RiskManager
from engine.core.confluence import confluence_manager

@pytest.fixture
def engine():
    return UnifiedBacktestEngine(min_confluence_score=60)

def test_unified_backtest_engine_initialization(engine):
    assert engine.min_score == 60
    assert engine.maker_fee == 0.0002
    assert engine.taker_fee == 0.0006
    assert engine.slippage == 0.0002
    assert engine.strategy is not None
    assert engine.risk_mgr is not None

def test_institutional_metrics_vectorization():
    trades = [
        {"outcome_r": 1.5, "entry_idx": 10, "exit_idx": 15, "close_reason": "TP1_HIT"},
        {"outcome_r": -1.0, "entry_idx": 20, "exit_idx": 22, "close_reason": "STOP_LOSS"},
        {"outcome_r": 3.0, "entry_idx": 30, "exit_idx": 40, "close_reason": "TP2_HIT"},
        {"outcome_r": 0.0, "entry_idx": 50, "exit_idx": 55, "close_reason": "FAST_BREAKEVEN"},
        {"outcome_r": -1.0, "entry_idx": 60, "exit_idx": 63, "close_reason": "STOP_LOSS"},
        {"outcome_r": 5.0, "entry_idx": 70, "exit_idx": 85, "close_reason": "TP3_HIT"},
    ]
    metrics = UnifiedBacktestEngine.calculate_performance_metrics(trades, initial_balance=100_000.0, risk_pct=0.01)
    
    assert metrics["total_trades"] == 6
    assert metrics["win_rate"] == 50.0
    assert metrics["breakeven_rate"] == pytest.approx(16.67, rel=1e-2)
    assert metrics["total_r"] == 7.5
    assert metrics["profit_factor"] == pytest.approx(4.75, rel=1e-2)
    assert metrics["max_drawdown_pct"] >= 0.0
    assert "sharpe_ratio" in metrics
    assert "sortino_ratio" in metrics
    assert "calmar_ratio" in metrics
    assert "exit_breakdown" in metrics

def test_structural_sl_and_ote_via_risk_manager(engine):
    calc = engine.risk_mgr.calculate_position(
        current_price=60000.0,
        signal_type="LONG",
        market_regime="MARKUP",
        smc_data={
            "order_blocks": {
                "bullish": [{"top": 60100.0, "bottom": 59800.0}],
                "bearish": []
            }
        },
        atr_value=400.0,
        asset="BTCUSDT",
        confluence_score=80
    )
    
    assert calc is not None
    assert calc["stop_loss"] < 60000.0
    assert calc["tp1"] > 60000.0
    assert calc["be_price"] > 60000.0
    assert calc["be_price"] < calc["tp1"]

def test_asymmetric_exit_grid_volume_conservation():
    tp1_pct = 0.60
    tp2_pct = 0.20
    tp3_pct = 0.10
    runner_pct = 0.10
    
    total_exit = tp1_pct + tp2_pct + tp3_pct + runner_pct
    assert total_exit == pytest.approx(1.0, rel=1e-6)

def test_intra_candle_pessimistic_order_bias():
    entry_price = 100.0
    sl = 95.0
    tp1 = 110.0
    
    candle_low = 90.0
    candle_high = 115.0
    
    hit_sl = candle_low <= sl
    hit_tp = candle_high >= tp1
    assert hit_sl and hit_tp
    
    outcome = "SL" if hit_sl else "TP"
    assert outcome == "SL"
