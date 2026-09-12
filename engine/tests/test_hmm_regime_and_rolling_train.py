"""
engine/tests/test_hmm_regime_and_rolling_train.py
=================================================
Suite de pruebas para el Detector de Régimen HMM/GMM y el Reentrenador Walk-Forward
continuo con Hot-Reload (SOP-75 / Slingshot v53.0).
"""

import pytest
import numpy as np
import pandas as pd
from engine.agents.regime_hmm import GaussianHMMRegimeDetector, ProbabilisticRegime
from engine.ml.inference import SlingshotML
from engine.ml.train_rolling import RollingWalkForwardTrainer


def generate_synthetic_candles(n: int = 150, trend: float = 0.05, vol: float = 1.0) -> pd.DataFrame:
    """Genera serie de velas sintética para testeo determinístico."""
    np.random.seed(42)
    dates = pd.date_range("2026-01-01", periods=n, freq="15min")
    returns = np.random.normal(trend / 100.0, vol / 100.0, n)
    price = 100.0 * np.cumprod(1.0 + returns)

    high = price * (1.0 + np.abs(np.random.normal(0, 0.002, n)))
    low = price * (1.0 - np.abs(np.random.normal(0, 0.002, n)))
    open_p = (high + low) / 2.0
    volume = np.random.uniform(500, 2000, n)

    return pd.DataFrame({
        "timestamp": dates,
        "open": open_p,
        "high": high,
        "low": low,
        "close": price,
        "volume": volume
    })


def test_hmm_feature_extraction():
    """Verifica que la extracción de features para HMM produce la matriz adecuada."""
    detector = GaussianHMMRegimeDetector()
    df = generate_synthetic_candles(60)
    features = detector.extract_features(df)

    assert features.shape[0] == 60
    assert features.shape[1] == 4
    assert not np.isnan(features).any()


def test_hmm_fit_and_prediction():
    """Verifica que el modelo probabilístico HMM clasifica y asigna probabilidades normalizadas."""
    detector = GaussianHMMRegimeDetector()
    df = generate_synthetic_candles(150, trend=0.1, vol=0.5)

    success = detector.fit_from_candles(df)
    assert success is True

    state = detector.predict_regime_state(df)
    assert state.primary_regime in list(ProbabilisticRegime)
    assert 0.50 <= state.risk_multiplier <= 1.35
    assert 0.0 <= state.confidence <= 1.0

    # La suma de probabilidades debe ser aproximadamente 1.0
    prob_sum = sum(state.regime_probabilities.values())
    assert pytest.approx(prob_sum, abs=0.01) == 1.0


def test_slingshot_ml_hot_reload_interface():
    """Verifica que SlingshotML cuenta con el método reload_model para Hot-Reload sin caídas."""
    ml = SlingshotML()
    assert hasattr(ml, "reload_model")
    # Si existe el archivo, reload_model debe retornar bool sin lanzar excepciones
    res = ml.reload_model("slingshot_xgb_15m_v2.json")
    assert isinstance(res, bool)


def test_rolling_walk_forward_pipeline_validation():
    """Verifica la lógica del pipeline Walk-Forward con datos sintéticos."""
    trainer = RollingWalkForwardTrainer(min_accuracy=0.50, window_candles=600, n_splits=3)
    df = generate_synthetic_candles(600, trend=0.05, vol=0.8)

    ml_dataset = trainer.engineer.prepare_dataset(df, classification=True)
    to_drop = ["timestamp", "open", "high", "low", "close", "number_of_trades", "TARGET"]
    feature_cols = [c for c in ml_dataset.columns if c not in to_drop and pd.api.types.is_numeric_dtype(ml_dataset[c])]

    X = ml_dataset[feature_cols]
    y = ml_dataset["TARGET"]

    mean_acc, mean_prec, model = trainer.execute_walk_forward_validation(X, y)
    assert 0.0 <= mean_acc <= 1.0
    assert 0.0 <= mean_prec <= 1.0
    assert model is not None
