"""
engine/tests/test_multi_year_regime_analog_orchestrator.py
==========================================================
Tests unitarios del orquestador de ciclos multi-año y escenarios análogos históricos.
"""

import pytest
from engine.analytics.multi_year_regime_analog_orchestrator import (
    MultiYearRegimeAnalogOrchestrator,
    HistoricalCycleAnalog
)


def test_multi_year_orchestrator_initialization():
    orchestrator = MultiYearRegimeAnalogOrchestrator()
    assert len(orchestrator.canonical_cycles) >= 4
    
    cycle_ids = [c.cycle_id for c in orchestrator.canonical_cycles]
    assert "cycle_2020_2021_post_halving_ath" in cycle_ids
    assert "cycle_2022_2023_bear_to_bull_recovery" in cycle_ids
    assert "cycle_2024_etf_reaccumulation" in cycle_ids
    assert "cycle_2025_2026_pre_expansion" in cycle_ids


def test_evaluate_current_market_fingerprint():
    orchestrator = MultiYearRegimeAnalogOrchestrator()
    res = orchestrator.evaluate_current_market_fingerprint(
        current_btc_price=84600.0,
        current_adx=24.5,
        current_ker=0.44,
        btc_volatility_10d=6.7,
        days_in_current_range=18
    )

    assert "macroCycleStage" in res
    assert "Consolidación de Rango Alto" in res["macroCycleStage"]
    assert len(res["historicalAnalogs"]) == 4
    assert len(res["projectedNextPhases"]) == 3
    assert len(res["institutionalAdjustments"]) == 4

    top_analog = res["historicalAnalogs"][0]
    assert top_analog["similarityScore"] >= 80.0
    assert "strategyPerformance" in top_analog
    assert top_analog["strategyPerformance"]["profit_factor"] > 1.0


def test_historical_cycle_lessons_consistency():
    orchestrator = MultiYearRegimeAnalogOrchestrator()
    for cycle in orchestrator.canonical_cycles:
        assert len(cycle.key_lessons) >= 3
        assert cycle.strategy_performance["trades_count"] > 100
        assert cycle.strategy_performance["net_r"] > 0
        assert cycle.btc_behavior["max_range_duration_days"] > 0
