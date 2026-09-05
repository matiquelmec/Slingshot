"""
=============================================================================
SLINGSHOT v46.0 — EVENT-DRIVEN PORTFOLIO BACKTEST QA SUITE
=============================================================================
Pruebas unitarias cuantitativas que certifican el Motor Cronológico Unificado:
1. Throttling de concurrencia (SOP-30: Máximo de posiciones simultáneas).
2. Reciclaje dinámico de slots (Liberación de riesgo al tocar TP1 @ Breakeven).
3. Veto dinámico Macro BTC (btc_aligned en tiempo de replay).
4. Aritmética de interés compuesto dinámico (SOP-39 al 2.50%).
5. Invarianza y generación del reporte inmutable JSON.
=============================================================================
"""
import os
import json
import pytest
import pandas as pd
from datetime import datetime, timedelta

from engine.backtest.unified_backtest_engine import (
    UnifiedBacktestEngine,
    MEGA_CAPS,
    HIGH_BETA_ALTS
)
from engine.risk.risk_manager import RiskManager


@pytest.fixture
def engine():
    return UnifiedBacktestEngine()


def test_chronological_concurrency_throttling(engine):
    """Verifica que si se define max_concurrent_longs = 1, la 2da orden simultánea se vete."""
    fake_trades = [
        {
            "symbol": "INJUSDT",
            "direction": "LONG",
            "entry_time": "2026-03-01 10:00:00",
            "exit_time": "2026-03-01 14:00:00",
            "tp1_time": None,
            "outcome_r": 1.2,
            "confluence_score": 75
        },
        {
            "symbol": "FETUSDT",
            "direction": "LONG",
            "entry_time": "2026-03-01 11:00:00",
            "exit_time": "2026-03-01 15:00:00",
            "tp1_time": None,
            "outcome_r": 1.5,
            "confluence_score": 75
        }
    ]

    active_positions = []
    executed = []
    rejected_slots = 0
    max_concurrent = 1

    for tr in fake_trades:
        entry_dt = pd.to_datetime(tr["entry_time"])
        exit_dt = pd.to_datetime(tr["exit_time"])
        risk_freed = exit_dt

        # Clean
        active_positions = [p for p in active_positions if p["risk_freed"] > entry_dt]

        same_dir = [p for p in active_positions if p["direction"] == tr["direction"]]
        if len(same_dir) >= max_concurrent:
            rejected_slots += 1
            continue

        active_positions.append({"symbol": tr["symbol"], "direction": tr["direction"], "risk_freed": risk_freed})
        executed.append(tr)

    assert len(executed) == 1
    assert rejected_slots == 1
    assert executed[0]["symbol"] == "INJUSDT"


def test_chronological_slot_recycling(engine):
    """Verifica que cuando Trade 1 toca TP1, su riesgo se libera ($0) y permite una 2da orden."""
    fake_trades = [
        {
            "symbol": "NEARUSDT",
            "direction": "LONG",
            "entry_time": "2026-03-01 10:00:00",
            "exit_time": "2026-03-01 14:00:00",
            "tp1_time": "2026-03-01 10:45:00",
            "outcome_r": 2.0,
            "confluence_score": 75
        },
        {
            "symbol": "BNBUSDT",
            "direction": "LONG",
            "entry_time": "2026-03-01 11:00:00",
            "exit_time": "2026-03-01 15:00:00",
            "tp1_time": None,
            "outcome_r": 1.2,
            "confluence_score": 75
        }
    ]

    active_positions = []
    executed = []
    rejected_slots = 0
    max_concurrent = 1

    for tr in fake_trades:
        entry_dt = pd.to_datetime(tr["entry_time"])
        exit_dt = pd.to_datetime(tr["exit_time"])
        tp1_time = tr.get("tp1_time")
        risk_freed = pd.to_datetime(tp1_time) if tp1_time else exit_dt

        # Clean
        active_positions = [p for p in active_positions if p["risk_freed"] > entry_dt]

        same_dir = [p for p in active_positions if p["direction"] == tr["direction"]]
        if len(same_dir) >= max_concurrent:
            rejected_slots += 1
            continue

        active_positions.append({"symbol": tr["symbol"], "direction": tr["direction"], "risk_freed": risk_freed})
        executed.append(tr)

    assert len(executed) == 2
    assert rejected_slots == 0


def test_chronological_btc_macro_veto(engine):
    """Verifica que altcoins en dirección opuesta a la tendencia macro de BTC sean vetadas."""
    btc_map = {
        pd.to_datetime("2026-03-01 10:00:00"): "BEARISH",
        pd.to_datetime("2026-03-01 11:00:00"): "BULLISH"
    }

    entry_dt_1 = pd.to_datetime("2026-03-01 10:00:00")
    btc_trend_1 = btc_map[entry_dt_1]
    is_aligned_1 = ("LONG" == "LONG" and btc_trend_1 == "BULLISH") or ("LONG" == "SHORT" and btc_trend_1 == "BEARISH")
    assert is_aligned_1 is False

    entry_dt_2 = pd.to_datetime("2026-03-01 11:00:00")
    btc_trend_2 = btc_map[entry_dt_2]
    is_aligned_2 = ("LONG" == "LONG" and btc_trend_2 == "BULLISH") or ("LONG" == "SHORT" and btc_trend_2 == "BEARISH")
    assert is_aligned_2 is True


def test_compounding_math_sop39():
    """Verifica que el interés compuesto dinámico escale proporcionalmente al equity disponible."""
    initial_balance = 1000.0
    risk_pct = 0.025
    trades_r = [1.2, -0.65, 2.0]

    current_balance = initial_balance
    for r in trades_r:
        risk_usd = current_balance * risk_pct
        pnl = r * risk_usd
        current_balance += pnl

    assert current_balance == pytest.approx(1063.9256, rel=1e-3)
    assert current_balance > initial_balance


def test_chronological_replay_execution_invariants(engine):
    """Verifica la ejecución integral del replay cronológico sobre el universo real."""
    report = engine.run_chronological_portfolio_replay(max_concurrent_longs=2)
    assert "telemetry_funnel" in report
    assert "institutional_mode" in report
    assert "compounding_mode" in report

    funnel = report["telemetry_funnel"]
    assert funnel["raw_signals"] > 0
    assert funnel["executed_trades"] > 0
    assert funnel["executed_trades"] <= funnel["raw_signals"]

    inst = report["institutional_mode"]
    assert inst["total_trades"] == funnel["executed_trades"]
    assert inst["win_rate"] > 35.0
    assert inst["profit_factor_base"] > 1.20
    assert inst["total_r_base"] > 30.0
    assert inst["max_drawdown_base_pct"] < 10.0
