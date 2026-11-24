"""
SOP-151 Prop-Firm Apex Verification Suite:
1. PropFirmGovernor: Tier-1 universe, Core-to-MT5 map, Near-Target Dampener & Consistency Cap
2. FtmoGuardianShield: Hard Equity Flatten @ -3.8% & Victory Lock @ +10.10%
3. MT5Bridge: Single-Ticket Anti-Splitting mode & close_all_open_positions
4. PropFirmPassSimulator: Monte Carlo survival & pass rate validation
"""

from unittest.mock import patch
from engine.risk.prop_firm_governor import (
    PropFirmGovernor,
    PROP_FIRM_TIER1_CRYPTO_UNIVERSE,
)
from engine.risk.ftmo_guardian import FtmoGuardianShield
from engine.execution.mt5_bridge import MT5Bridge
from engine.analytics.prop_firm_pass_simulator import PropFirmPassSimulator


def test_prop_firm_governor_universe_and_risk_rules():
    gov = PropFirmGovernor(min_trading_days=4, near_target_threshold_pct=85.0, max_daily_profit_share_pct=35.0)
    assert len(PROP_FIRM_TIER1_CRYPTO_UNIVERSE) == 8
    assert gov.is_prop_tier1_asset("ETHUSDT") is True
    assert gov.is_prop_tier1_asset("FETUSDT") is False
    assert gov.map_core_to_mt5_symbol("BTCUSDT") == "BTCUSD"
    assert gov.map_core_to_mt5_symbol("XAUUSDT") == "XAUUSD"
    assert gov.map_core_to_mt5_symbol("BNBUSDT") is None

    # Near-Target Dampener (>= 85% of target -> 50% risk reduction)
    r_damp, reason_damp = gov.compute_prop_adjusted_risk_pct(0.0075, progress_pct=88.0, daily_profit_pct=1.0, target_pct=10.0)
    assert r_damp == 0.00375
    assert "NEAR_TARGET_DAMPENER" in reason_damp

    # Consistency Cap (35% of 10% = 3.5% daily profit)
    r_cap, reason_cap = gov.compute_prop_adjusted_risk_pct(0.0075, progress_pct=50.0, daily_profit_pct=3.6, target_pct=10.0)
    assert r_cap == 0.0
    assert "CONSISTENCY_CAP_REACHED" in reason_cap


def test_ftmo_guardian_hard_flatten_and_victory_lock(tmp_path):
    state_file = str(tmp_path / "ftmo_state.json")
    guardian = FtmoGuardianShield(account_size=100000.0, phase="PHASE_1", state_file=state_file)
    guardian.daily_starting_equity = 100000.0
    guardian.min_trading_days = 4
    guardian.trading_days_count = 4

    with patch.object(guardian, "_flatten_mt5_positions_on_emergency") as mock_flatten:
        # 1. Hard Equity Flatten at -3.8% daily drawdown
        res_dd = guardian.update_equity(96150.0)
        assert res_dd["is_daily_lockout"] is True
        mock_flatten.assert_called_once_with("HARD_DAILY_DD_3_8PCT")

    # 2. Victory Lock at +10.10% in Phase 1
    g2 = FtmoGuardianShield(account_size=100000.0, phase="PHASE_1", state_file=str(tmp_path / "ftmo_win.json"))
    g2.daily_starting_equity = 110000.0
    g2.min_trading_days = 4
    g2.trading_days_count = 4
    with patch.object(g2, "_flatten_mt5_positions_on_emergency") as mock_win_flatten:
        res_win = g2.update_equity(110150.0)
        assert res_win["is_target_locked"] is True
        assert res_win["is_daily_lockout"] is True
        mock_win_flatten.assert_called_once_with("VICTORY_LOCK")


def test_mt5_bridge_single_ticket_mode():
    bridge = MT5Bridge(dry_run=True)
    res = bridge.place_limit_order(
        symbol="XAUUSD",
        direction="LONG",
        entry_price=2650.0,
        stop_loss=2630.0,
        tp1=2676.0,
        tp2=2700.0,
        tp3=2730.0,
        single_ticket_mode=True,
    )
    assert res["success"] is True
    assert len(res["orders"]) == 1
    assert res["orders"][0]["label"] == "SINGLE_APEX"


def test_prop_firm_pass_simulator_survival_grid():
    sim = PropFirmPassSimulator()
    r_series = sim.load_audited_r_series(prop_tier1_only=True)
    assert len(r_series) > 5
    out = sim.simulate_risk_grid(r_series, risk_grid_pct=[0.50, 2.50], n_trials=200, seed=7)
    assert out["optimal_risk_pct"] in (0.50, 2.50)
    by_r = {r["risk_per_trade_pct"]: r for r in out["results"]}
    assert by_r[0.50]["bust_rate_pct"] <= by_r[2.50]["bust_rate_pct"]
