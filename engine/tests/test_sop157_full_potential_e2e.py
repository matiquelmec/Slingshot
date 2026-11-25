import numpy as np
import pandas as pd

from engine.core.strategy_ssot import BITUNIX_CANONICAL_BASE_RISK_PCT
from engine.indicators.tradfi_smc_engine import evaluate_tradfi_bar, prepare_tradfi_features


def _make_df(n: int = 260, freq: str = "1h", slope: float = 120.0) -> pd.DataFrame:
    ts = pd.date_range("2026-01-01", periods=n, freq=freq, tz="UTC")
    base = 2000.0 + np.linspace(0.0, slope, n) + np.sin(np.arange(n) * 0.25) * 6.0
    return pd.DataFrame({
        "timestamp": ts,
        "open": base - 1.5,
        "high": base + 3.0,
        "low": base - 3.0,
        "close": base + 1.5,
        "volume": np.full(n, 1500.0),
    })


def test_tradfi_1d_smt_vwap_strict_causality():
    df_1h = _make_df(260, "1h", 120.0)
    df_1d = _make_df(80, "1d", 300.0)
    df_sis = _make_df(260, "1h", 110.0)

    feat_full = prepare_tradfi_features(df_1h, htf_1d_df=df_1d, sister_df=df_sis)
    feat_trunc = prepare_tradfi_features(df_1h.iloc[:230].copy(), htf_1d_df=df_1d, sister_df=df_sis.iloc[:230].copy())

    assert "session_vwap" in feat_full.columns
    assert "htf_trend" in feat_full.columns
    assert "smt_bull" in feat_full.columns

    r_full = evaluate_tradfi_bar(feat_full, idx=229, symbol="XAUUSD", archetype="IMPULSE_OTE_SMC")
    r_trunc = evaluate_tradfi_bar(feat_trunc, idx=229, symbol="XAUUSD", archetype="IMPULSE_OTE_SMC")
    assert (r_full is None) == (r_trunc is None)


def test_bitunix_sop147_frozen_risk_preserved():
    assert BITUNIX_CANONICAL_BASE_RISK_PCT == 0.025
