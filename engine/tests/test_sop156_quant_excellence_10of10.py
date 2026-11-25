import numpy as np

from engine.analytics.live_forward_tracker import LiveForwardTracker, LiveTradeObservation
from engine.analytics.prop_firm_pass_simulator import PropFirmPassSimulator
from engine.analytics.quant_statistical_rigor import (
    compute_deflated_sharpe_ratio,
    compute_wald_sprt,
    run_cpcv_validation,
    stationary_bootstrap_sample,
)
from engine.risk.prop_firm_governor import FTMO_MT5_APPROVED_MATRIX, prop_firm_governor


def test_deflated_sharpe_and_cpcv_15_folds():
    rng = np.random.default_rng(7)
    strong_edge = (rng.normal(0.30, 0.80, size=120)).tolist()
    dsr = compute_deflated_sharpe_ratio(strong_edge, num_trials=15)
    assert dsr["dsr"] > 0.85

    cpcv = run_cpcv_validation(strong_edge, n_splits=6, k_test=2, embargo_pct=0.02)
    assert cpcv["n_folds"] == 15
    assert cpcv["fold_positive_rate_pct"] >= 80.0
    assert cpcv["pbo_score"] <= 0.25


def test_stationary_bootstrap_and_wald_sprt():
    items = [{"net_r": 0.2, "worst_intraday_r": -0.5, "trades": 1} for _ in range(20)]
    sample = stationary_bootstrap_sample(items, target_len=365, mean_block_len=5.0)
    assert len(sample) == 365

    sprt_pos = compute_wald_sprt([0.35] * 25, mu0=0.0, mu1=0.25, sigma=0.985)
    assert sprt_pos["sprt_decision"] == "EDGE_CERTIFIED"
    assert sprt_pos["sprt_log_likelihood"] >= sprt_pos["sprt_upper_bound"]

    sprt_neg = compute_wald_sprt([-0.65] * 20, mu0=0.0, mu1=0.25, sigma=0.985)
    assert sprt_neg["sprt_decision"] == "EDGE_DECAY_ALERT"


def test_cluster_mutex_xau_xag_and_tier_weighting():
    ok_xag, msg = prop_firm_governor.is_cluster_slot_available("XAGUSD", ["XAUUSD"])
    assert ok_xag is False
    assert "SAFE_HAVEN_METALS" in msg

    assert FTMO_MT5_APPROVED_MATRIX["UK100"]["tier_weight"] == 0.65
    assert FTMO_MT5_APPROVED_MATRIX["XAUUSD"]["tier_weight"] == 1.00


def test_live_forward_tracker_includes_wald_sprt():
    tracker = LiveForwardTracker(parameter_freeze_date="2026-11-18")
    obs = [
        LiveTradeObservation(
            symbol="ETHUSDT",
            direction="LONG",
            closed_at="2026-11-20T10:00:00Z",
            signal_entry_price=3000.0,
            fill_entry_price=3000.0,
            risk_usd=25.0,
            gross_pnl_usd=15.0,
        )
        for _ in range(5)
    ]
    summary = tracker.evaluate_live_trades(obs)
    assert summary.sprt_log_likelihood > 0.0
    assert summary.sprt_decision == "CONTINUE_SAMPLING"


def test_prop_firm_simulator_v4_stationary_unlimited():
    clusters = PropFirmPassSimulator.load_daily_clusters(profile="FTMO_SWING")
    sim = PropFirmPassSimulator().simulate_risk_grid(clusters, risk_grid_pct=[0.75], n_trials=200)
    row = sim["results"][0]
    assert "funded_within_90d_pct" in row
    assert "funded_within_180d_pct" in row
    assert row["funded_pass_rate_pct"] >= row["funded_within_180d_pct"]
