import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
from pathlib import Path

from engine.agents.regime_agent import SlingshotRegimeAgent, MarketRegime, RegimeAssessment
from engine.core.vault import SlingshotVault
from engine.ml.drift_monitor import DriftReport
from engine.risk.risk_manager import RiskManager


def test_regime_agent_classification_expansion_vs_chop(tmp_path):
    agent = SlingshotRegimeAgent()
    
    # 1. Caso Mercado en Expansión Fuerte (ADX alto, KER alto, tendencia alcista)
    df_bull = pd.DataFrame({
        "close": np.linspace(100, 150, 30),
        "adx": [28.0] * 30,
        "ker": [0.65] * 30
    })
    
    assessment_bull = agent.evaluate_market_regime(
        symbols_data={"BTCUSDT": df_bull, "SOLUSDT": df_bull},
        btc_htf_trend="BULLISH"
    )
    
    assert assessment_bull.regime == MarketRegime.BULL_EXPANSION
    assert assessment_bull.risk_multiplier >= 1.25
    assert "Expansión alcista institucional" in assessment_bull.actionable_guideline
    
    # 2. Caso Mercado en Compresión / Chop Muerto (ADX < 18, KER < 0.28)
    df_chop = pd.DataFrame({
        "close": [100.0 + (i % 2) * 0.1 for i in range(30)],
        "adx": [15.0] * 30,
        "ker": [0.15] * 30
    })
    
    assessment_chop = agent.evaluate_market_regime(
        symbols_data={"BTCUSDT": df_chop, "ETHUSDT": df_chop},
        btc_htf_trend="NEUTRAL"
    )
    
    assert assessment_chop.regime == MarketRegime.CHOP_COMPRESSION
    assert assessment_chop.risk_multiplier <= 0.75
    assert "Mercado lateral comprimido" in assessment_chop.actionable_guideline


def test_regime_agent_drift_triggers_auto_retrain():
    agent = SlingshotRegimeAgent()
    
    # Reporte de drift estable: NO debe disparar reentrenamiento
    stable_report = DriftReport(
        drift_level="STABLE",
        alert_triggered=False,
        psi_max=0.05,
        rolling_accuracy=0.62
    )
    with patch("engine.agents.regime_agent.safe_auto_retrain") as mock_retrain:
        res = agent.check_ml_health_and_trigger_retrain(stable_report)
        assert res is False
        mock_retrain.assert_not_called()

    # Reporte de drift severo: DEBE disparar reentrenamiento seguro
    severe_report = DriftReport(
        drift_level="SEVERE",
        alert_triggered=True,
        psi_max=0.35,
        rolling_accuracy=0.40
    )
    with patch("engine.agents.regime_agent.safe_auto_retrain", return_value=(True, "Modelo reentrenado")) as mock_retrain:
        res = agent.check_ml_health_and_trigger_retrain(severe_report)
        assert res is True
        mock_retrain.assert_called_once()


def test_vault_persists_and_recovers_regime_state(tmp_path):
    db_file = tmp_path / "test_regime_vault.db"
    test_vault = SlingshotVault(db_path=db_file)
    
    # Registrar estado
    test_vault.record_regime_state(
        regime="BULL_EXPANSION",
        risk_multiplier=1.30,
        confidence=0.88,
        details={"adx": 30.5, "ker": 0.62, "guideline": "Runners a +5R"}
    )
    
    # Recuperar último estado
    latest = test_vault.get_latest_regime_state()
    assert latest is not None
    assert latest["regime"] == "BULL_EXPANSION"
    assert latest["risk_multiplier"] == 1.30
    assert latest["confidence"] == 0.88
    assert latest["details"]["adx"] == 30.5
    
    # Verificar integración con calculate_alpha_tier_sizing
    base_sizing = RiskManager.calculate_alpha_tier_sizing("BTCUSDT", confluence_score=75.0)
    modulated_sizing = RiskManager.calculate_alpha_tier_sizing(
        "BTCUSDT",
        confluence_score=75.0,
        regime_mult=latest["risk_multiplier"]
    )
    assert modulated_sizing > base_sizing
