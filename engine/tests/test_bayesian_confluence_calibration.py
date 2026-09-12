"""
engine/tests/test_bayesian_confluence_calibration.py
====================================================
Suite de pruebas unitarias y de integración para el Calibrador Bayesiano
Dinámico de Confluencias (SOP-74 / Slingshot v53.0).
"""

import time
import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from engine.core.bayesian_confluence import (
    BayesianConfluenceCalibrator,
    DEFAULT_BASE_WEIGHTS,
    CHECKLIST_TO_WEIGHT_KEY,
)
from engine.core.vault import SlingshotVault
from engine.core.confluence import ConfluenceManager


@pytest.fixture
def temp_vault(tmp_path):
    """Bóveda de pruebas aislada en base de datos temporal."""
    db_file = tmp_path / "test_vault.db"
    v = SlingshotVault(db_path=db_file)
    return v


@pytest.fixture
def calibrator(temp_vault):
    """Instancia limpia de calibrador con boveda temporal."""
    cal = BayesianConfluenceCalibrator(
        vault=temp_vault,
        alpha_prior=10.0,
        beta_prior=10.0,
        min_multiplier=0.50,
        max_multiplier=1.60,
        rolling_window=50,
    )
    # Limpiar estado interno
    with cal._lock:
        cal._calibrated_weights = dict(DEFAULT_BASE_WEIGHTS)
        for k, w in DEFAULT_BASE_WEIGHTS.items():
            cal._factor_stats[k] = {
                "base_weight": w,
                "calibrated_weight": w,
                "wins": 0,
                "losses": 0,
                "posterior_win_rate": 0.50,
                "multiplier": 1.0,
                "sample_size": 0,
            }
    return cal


def test_initial_base_weights(calibrator):
    """Verifica que los pesos iniciales corresponden a los canónicos de Slingshot."""
    assert calibrator.get_weight("narrative_weight") == 15.0
    assert calibrator.get_weight("poi_weight") == 40.0
    assert calibrator.get_weight("vol_weight") == 15.0
    assert calibrator.get_weight("ml_weight") == 10.0
    assert calibrator.get_weight("Zonas POI") == 40.0  # Vía alias legible


def test_bayesian_win_rate_increase_on_winning_streak(calibrator):
    """
    Verifica que al atribuir trades ganadores a un factor, su probabilidad posterior
    y su peso ponderado aumentan de forma acotada y suave.
    """
    checklist = [
        {"factor": "Zonas POI", "status": "CONFIRMADO"},
        {"factor": "Huella RVOL", "status": "CONFIRMADO"},
    ]

    # Simular 10 trades ganadores consecutivos con POI presente
    for i in range(10):
        calibrator.record_trade_attribution(
            trade_id=f"win_trade_{i}",
            symbol="BTCUSDT",
            active_checklist=checklist,
            is_win=True,
            pnl_r=2.0,
        )

    poi_weight = calibrator.get_weight("poi_weight")
    stats = calibrator.get_factor_stats()["poi_weight"]

    # Con 10 victorias: alpha = 10 + 10 = 20, beta = 10 -> E[p] = 20/30 = 0.6667
    assert stats["wins"] == 10
    assert stats["losses"] == 0
    assert stats["posterior_win_rate"] == pytest.approx(0.6667, abs=0.01)
    assert stats["multiplier"] == pytest.approx(0.6667 / 0.50, abs=0.02)
    # El peso base de 40 sube a aproximadamente 53
    assert poi_weight > 40.0
    assert poi_weight == pytest.approx(53.0, abs=2.0)


def test_bayesian_weight_decrease_on_losing_streak(calibrator):
    """
    Verifica que cuando un factor falla recurrentemente, el calibrador devalúa
    su peso dinámicamente, respetando el suelo de seguridad (min_multiplier = 0.50).
    """
    checklist = [
        {"factor": "Tendencia 4H HTF", "status": "CONFIRMADO"},
    ]

    # Simular 30 trades perdedores consecutivos
    for i in range(30):
        calibrator.record_trade_attribution(
            trade_id=f"loss_trade_{i}",
            symbol="ETHUSDT",
            active_checklist=checklist,
            is_win=False,
            pnl_r=-1.0,
        )

    htf_weight = calibrator.get_weight("htf_weight")
    stats = calibrator.get_factor_stats()["htf_weight"]

    # Con 30 derrotas: alpha = 10, beta = 10 + 30 = 40 -> E[p] = 10/50 = 0.20
    # Multiplicador raw = 0.20 / 0.50 = 0.40, pero debe estar acotado a min_multiplier = 0.50
    assert stats["losses"] == 30
    assert stats["multiplier"] == 0.50  # Clamped al mínimo de seguridad
    assert htf_weight == pytest.approx(15.0 * 0.50, abs=1.0)  # 8 pts


def test_microsecond_latency_benchmark(calibrator):
    """
    Benchmark crítico: Garantiza que la consulta de pesos en memoria toma
    menos de 0.01 ms por llamada para no impactar el bucle asíncrono de ticks.
    """
    n_iterations = 20000
    start = time.perf_counter()
    for _ in range(n_iterations):
        _ = calibrator.get_weight("poi_weight")
        _ = calibrator.get_weight("narrative_weight")
        _ = calibrator.get_weight("vol_weight")
    elapsed = time.perf_counter() - start

    avg_latency_us = (elapsed / (n_iterations * 3)) * 1_000_000
    # La latencia media debe ser inferior a 10 microsegundos (0.01 ms)
    assert avg_latency_us < 10.0, f"Latencia demasiado alta: {avg_latency_us:.2f} µs"


def test_confluence_manager_emits_calibration_telemetry():
    """
    Verifica que evaluate_signal incluye los metadatos de calibración bayesiana
    y respeta el contrato de interfaz.
    """
    cm = ConfluenceManager()
    dates = pd.date_range("2026-01-01", periods=100, freq="15min")
    df = pd.DataFrame({
        "timestamp": dates,
        "open": np.linspace(100, 110, 100),
        "high": np.linspace(101, 111, 100),
        "low": np.linspace(99, 109, 100),
        "close": np.linspace(100.5, 110.5, 100),
        "volume": [1000.0] * 100,
        "market_regime": ["MARKUP"] * 100,
    })

    sig = {
        "asset": "BTCUSDT",
        "signal_type": "LONG",
        "price": 110.5,
        "timestamp": dates[-1],
    }

    res = cm.evaluate_signal(df=df, signal=sig)
    assert "calibration" in res
    assert res["calibration"]["mode"] == "BAYESIAN_ADAPTIVE"
    assert "weights" in res["calibration"]
    assert "poi_weight" in res["calibration"]["weights"]
    assert res["score"] >= 0
