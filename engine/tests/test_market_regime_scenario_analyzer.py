"""
engine/tests/test_market_regime_scenario_analyzer.py
===================================================
Tests unitarios del analizador de régimen de mercado, búsqueda de escenarios análogos
y proyección de ajustes futuros (SSoT v60.0).
"""

import pytest
from engine.analytics.market_regime_scenario_analyzer import (
    MarketRegimeScenarioAnalyzer,
    MarketPhase
)


def test_detect_current_phase_bull_expansion():
    analyzer = MarketRegimeScenarioAnalyzer()
    res = analyzer.detect_current_phase(
        btc_price_change_20d=4.2,
        market_adx=26.0,
        market_ker=0.45,
        btc_htf_trend="BULLISH"
    )
    assert res["current_phase"] == MarketPhase.BULL_EXPANSION.value
    assert res["confidence"] >= 0.80
    assert "Expansión alcista estructurada" in res["summary"]


def test_detect_current_phase_chop_compression():
    analyzer = MarketRegimeScenarioAnalyzer()
    res = analyzer.detect_current_phase(
        btc_price_change_20d=0.2,
        market_adx=14.0,
        market_ker=0.18,
        btc_htf_trend="NEUTRAL"
    )
    assert res["current_phase"] == MarketPhase.CHOP_COMPRESSION.value
    assert res["confidence"] >= 0.85


def test_analyze_scenarios_from_backtest_analogous_projection():
    analyzer = MarketRegimeScenarioAnalyzer()
    mock_trades = [
        {"adx": 25.0, "ker": 0.45, "direction": "LONG", "btc_aligned": True, "outcome_r": 1.8},
        {"adx": 28.0, "ker": 0.42, "direction": "LONG", "btc_aligned": True, "outcome_r": -0.65},
        {"adx": 30.0, "ker": 0.50, "direction": "LONG", "btc_aligned": True, "outcome_r": 3.2},
        {"adx": 15.0, "ker": 0.15, "direction": "LONG", "btc_aligned": False, "outcome_r": -0.65},
        {"adx": 16.0, "ker": 0.18, "direction": "SHORT", "btc_aligned": False, "outcome_r": -0.65},
    ]

    analysis = analyzer.analyze_scenarios_from_backtest(
        trades=mock_trades,
        current_phase_name=MarketPhase.BULL_EXPANSION.value
    )

    assert analysis["current_phase"] == MarketPhase.BULL_EXPANSION.value
    assert analysis["is_adjustment_required"] is True
    assert "runner_ratchet_mode" in analysis["recommended_tuning"]
    
    analogous = analysis["analogous_scenario_performance"]
    assert analogous["trades_count"] == 3
    assert analogous["profit_factor"] > 2.0
    assert analogous["total_net_r"] > 0
