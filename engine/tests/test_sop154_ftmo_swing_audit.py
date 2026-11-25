from datetime import datetime, timezone
import numpy as np
import pandas as pd

from engine.analytics.prop_firm_pass_simulator import PropFirmPassSimulator
from engine.indicators.tradfi_smc_engine import evaluate_tradfi_bar, prepare_tradfi_features
from engine.risk.ftmo_guardian import FtmoGuardianShield
from engine.risk.prop_firm_governor import FTMO_MT5_APPROVED_MATRIX


def _make_synthetic_df(n: int = 260) -> pd.DataFrame:
    ts = pd.date_range("2026-01-01", periods=n, freq="1h", tz="UTC")
    base = 2000.0 + np.linspace(0.0, 120.0, n) + np.sin(np.arange(n) * 0.25) * 8.0
    return pd.DataFrame({
        "timestamp": ts,
        "open": base - 1.5,
        "high": base + 3.0,
        "low": base - 3.0,
        "close": base + 1.5,
        "volume": np.full(n, 1500.0),
    })


def test_tradfi_smc_engine_strict_causality():
    df_full = prepare_tradfi_features(_make_synthetic_df(260))
    df_trunc = prepare_tradfi_features(_make_synthetic_df(260).iloc[:230].copy())
    res_full = evaluate_tradfi_bar(df_full, idx=229, symbol="XAUUSD", archetype="IMPULSE_OTE_SMC")
    res_trunc = evaluate_tradfi_bar(df_trunc, idx=229, symbol="XAUUSD", archetype="IMPULSE_OTE_SMC")
    assert (res_full is None) == (res_trunc is None)
    if res_full is not None and res_trunc is not None:
        assert res_full["direction"] == res_trunc["direction"]
        assert abs(res_full["price"] - res_trunc["price"]) < 1e-6


def test_ftmo_guardian_dst_aware_prague_rollover_and_best_day():
    g = FtmoGuardianShield()
    # Invierno CET (UTC+1): 22:50 UTC == 23:50 CET -> dentro de ventana [23:45, 00:15]
    assert g.check_midnight_rollover_risk(22, 50, now_utc=datetime(2026, 1, 15, 22, 50, tzinfo=timezone.utc)) is True
    # Verano CEST (UTC+2): 22:10 UTC == 00:10 CEST -> dentro de ventana [23:45, 00:15]
    assert g.check_midnight_rollover_risk(22, 10, now_utc=datetime(2026, 7, 15, 22, 10, tzinfo=timezone.utc)) is True
    # Fuera de ventana en verano: 20:00 UTC == 22:00 CEST
    assert g.check_midnight_rollover_risk(20, 0, now_utc=datetime(2026, 7, 15, 20, 0, tzinfo=timezone.utc)) is False

    # Best-Day Diluter (> 35% -> 0.25%)
    assert g.compute_best_day_diluted_risk(0.0075, best_day_profit_usd=4000.0, total_profit_usd=8000.0) == 0.0025
    assert g.compute_best_day_diluted_risk(0.0075, best_day_profit_usd=2000.0, total_profit_usd=8000.0) == 0.0075


def test_ftmo_approved_matrix_and_simulator_profile():
    assert set(FTMO_MT5_APPROVED_MATRIX.keys()) == {"XAUUSD", "US100", "XAGUSD", "UK100"}
    assert FTMO_MT5_APPROVED_MATRIX["UK100"]["archetype"] == "LIQUIDITY_SWEEP_JUDAS"

    clusters = PropFirmPassSimulator.load_daily_clusters(profile="FTMO_SWING")
    assert len(clusters) > 50
    sim = PropFirmPassSimulator().simulate_risk_grid(clusters, risk_grid_pct=[0.50, 0.75], n_trials=200)
    assert sim["simulator_version"] == "SOP-152_DAILY_CLUSTERED_V2"
    assert len(sim["results"]) == 2
