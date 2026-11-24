"""
SOP-152 Scientific Prop-Firm Audit Verification Suite:
1. PropFirmPassSimulator v2: detects -5.0% intraday floating daily DD violations
2. PropFirmGovernor: SOP-152A Spread-to-Risk Gate (<= 8%) & SOP-152B Cross-Cluster Cap
3. Walk-Forward Benjamini-Hochberg FDR & no look-ahead bias
"""

from engine.analytics.prop_firm_pass_simulator import PropFirmPassSimulator
from engine.risk.prop_firm_governor import PropFirmGovernor
from engine.backtest.prop_firm_universe_audit import benjamini_hochberg_fdr


def test_prop_firm_simulator_v2_enforces_daily_5pct_dd():
    sim = PropFirmPassSimulator()
    # Día con -2.2R intradía: a 2.5% de riesgo = -5.5% -> debe reprobar por Daily DD (-5.0%)
    losing_day = [{"day": "2026-11-01", "net_r": -1.5, "worst_intraday_r": -2.2, "trades": 2}]
    out = sim.simulate_risk_grid(losing_day, risk_grid_pct=[0.50, 2.50], n_trials=50, block_size=1, seed=1)
    by_r = {r["risk_per_trade_pct"]: r for r in out["results"]}
    assert by_r[2.50]["fail_daily_dd_pct"] == 100.0
    assert by_r[2.50]["funded_pass_rate_pct"] == 0.0
    # A 0.50% de riesgo = -1.1% diario -> no viola el -5.0% diario
    assert by_r[0.50]["fail_daily_dd_pct"] == 0.0


def test_prop_firm_governor_sop152_spread_and_cluster_gates():
    gov = PropFirmGovernor()
    ok_spread, ratio_ok = gov.is_spread_to_risk_acceptable(entry_price=2650.0, stop_loss=2640.0, round_trip_cost_usd=0.25)
    assert ok_spread is True
    assert ratio_ok <= 0.08

    bad_spread, ratio_bad = gov.is_spread_to_risk_acceptable(entry_price=2650.0, stop_loss=2648.0, round_trip_cost_usd=0.25)
    assert bad_spread is False
    assert ratio_bad > 0.08

    # Cross-Cluster Cap: BTCUSDT y ETHUSDT comparten CRYPTO_BETA -> bloqueado; XAUUSD -> permitido
    ok_eth, _ = gov.is_cluster_slot_available("ETHUSDT", ["BTCUSDT"])
    ok_xau, _ = gov.is_cluster_slot_available("XAUUSD", ["BTCUSDT"])
    assert ok_eth is False
    assert ok_xau is True


def test_benjamini_hochberg_fdr_multiple_testing():
    flags = benjamini_hochberg_fdr([0.001, 0.02, 0.45, 0.80], alpha=0.10)
    assert flags == [True, True, False, False]
