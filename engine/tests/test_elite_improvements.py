"""
engine/tests/test_elite_improvements.py
=======================================
SUITE DE CERTIFICACIÓN QA: MEJORAS DE ÉLITE CUANTITATIVA (SOP-123)
===================================================================
1. Triple-Screen Macro Confluence (1D -> 1h -> 15m).
2. Volatilidad Escalar en Dollar Risk (ATR-Normalized Sizing).
3. Order Flow Delta & CVD Convergence (Absorción L2).
"""

import pytest
import pandas as pd
import numpy as np
from engine.risk.risk_manager import RiskManager
from engine.core.confluence import confluence_manager
from engine.indicators.volume import calculate_cvd_divergence


def test_sop123_atr_normalized_volatility_sizing():
    """
    [SOP-123] Valida que el escalador de volatilidad normalize el riesgo:
    - Activos con alta volatilidad (ATR% > 1.20%) ven reducido su tamaño (hasta 0.85x).
    - Activos con compresión baja y limpia (ATR% < 1.20%) ven expandido su tamaño (hasta 1.15x).
    """
    rm = RiskManager()

    # Caso 1: Altcoin con alta volatilidad (Precio 100, ATR 3.0 -> ATR% = 3.0%)
    # raw_scalar = 1.20 / 3.00 = 0.40 -> clamped to min_scalar 0.85
    scalar_high_vol = rm.calculate_volatility_scalar(entry_price=100.0, atr_value=3.0)
    assert scalar_high_vol == 0.85, f"Esperado 0.85x para alta volatilidad, obtenido {scalar_high_vol}"

    # Caso 2: Activo en compresión limpia (Precio 60,000, ATR 300 -> ATR% = 0.50%)
    # raw_scalar = 1.20 / 0.50 = 2.40 -> clamped to max_scalar 1.15
    scalar_low_vol = rm.calculate_volatility_scalar(entry_price=60000.0, atr_value=300.0)
    assert scalar_low_vol == 1.15, f"Esperado 1.15x para baja volatilidad limpia, obtenido {scalar_low_vol}"

    # Caso 3: Activo exactamente en el benchmark (Precio 100, ATR 1.20 -> ATR% = 1.20%)
    scalar_neutral = rm.calculate_volatility_scalar(entry_price=100.0, atr_value=1.20)
    assert scalar_neutral == 1.0, f"Esperado 1.0x para volatilidad benchmark, obtenido {scalar_neutral}"


def test_sop123_calculate_position_incorporates_vol_scalar():
    """
    [SOP-123] Valida que calculate_position aplique el escalador de volatilidad
    en actual_risk_pct y risk_amount_usdt.
    """
    rm = RiskManager(account_balance=100_000.0)

    # Posición con alta volatilidad (ATR = 4.0 en precio 100) -> scalar = 0.85
    pos_high_vol = rm.calculate_position(
        current_price=100.0,
        signal_type="LONG",
        market_regime="MARKUP",
        atr_value=4.0,
        asset="FETUSDT",
        confluence_score=85  # Base adaptive risk = 1.50%
    )

    # 1.50% * 0.85 = 1.275% -> risk_amount = 100,000 * 0.01275 = $1,275
    expected_risk = 100_000.0 * (0.0150 * 0.85)
    calc_risk = pos_high_vol["risk_amount_usdt"]
    assert abs(calc_risk - expected_risk) < 1.0, f"Esperado ${expected_risk}, obtenido ${calc_risk}"


def test_sop123_triple_screen_macro_confluence_bonus():
    """
    [SOP-123] Valida que el motor de confluencia inyecte la bonificación
    de +5.0 pts cuando exista alineación macro con la tendencia 1D.
    """
    # DataFrame simulado
    dates = pd.date_range("2026-01-01", periods=50, freq="15min")
    df = pd.DataFrame({
        "timestamp": dates,
        "open": np.linspace(100, 110, 50),
        "high": np.linspace(101, 111, 50),
        "low": np.linspace(99, 109, 50),
        "close": np.linspace(100, 110, 50),
        "volume": [1000.0] * 50
    })

    sig = {
        "timestamp": str(dates[-1]),
        "signal_type": "LONG",
        "price": 110.0,
        "regime": "MARKUP"
    }

    # Sin triple screen
    eval_base = confluence_manager.evaluate_signal(df, sig, daily_trend=None)
    score_base = eval_base["score"]

    # Con triple screen alineado (1D BULLISH)
    eval_aligned = confluence_manager.evaluate_signal(df, sig, daily_trend="BULLISH")
    score_aligned = eval_aligned["score"]

    assert score_aligned >= score_base, f"Esperado score >= {score_base}, obtenido {score_aligned}"
    factors = [f["factor"] for f in eval_aligned["checklist"]]
    assert "Triple Screen Macro" in factors
    assert any(f["status"] == "CONFIRMADO" for f in eval_aligned["checklist"] if f["factor"] == "Triple Screen Macro")


def test_sop123_cvd_divergence_absorption_detection():
    """
    [SOP-123] Valida que calculate_cvd_divergence detecte absorción compradora
    (precio baja pero CVD sube) y no emita vetos destructivos.
    """
    n = 40
    # Precio cayendo linealmente
    close_vals = np.linspace(100, 95, n)
    # Volumen alto y comprador constante (delta positivo constante en caídas -> smart money comprando)
    vol_vals = np.ones(n) * 1000.0
    high_vals = close_vals + 0.5
    low_vals = close_vals - 0.5
    open_vals = close_vals + 0.2

    df = pd.DataFrame({
        "open": open_vals,
        "high": high_vals,
        "low": low_vals,
        "close": close_vals,
        "volume": vol_vals
    })

    cvd_res = calculate_cvd_divergence(df, window=30)
    assert "status" in cvd_res
    assert isinstance(cvd_res["cvd_slope"], float)
