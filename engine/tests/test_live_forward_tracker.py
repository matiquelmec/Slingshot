"""
engine/tests/test_live_forward_tracker.py
Tests unitarios para el Tracker de Forward-Test en Vivo & Implementation Shortfall (SOP-146).
"""

from engine.analytics.live_forward_tracker import (
    LiveForwardTracker,
    LiveTradeObservation,
)
from engine.core.strategy_ssot import BITUNIX_CANONICAL_BASE_RISK_PCT


def test_preserves_canonical_250pct_base_risk():
    """Garantiza que el riesgo base de Bitunix se mantiene en 2.50% (0.025) por defecto."""
    assert BITUNIX_CANONICAL_BASE_RISK_PCT == 0.025


def test_live_forward_tracker_empty_sample_building():
    tracker = LiveForwardTracker(parameter_freeze_date="2026-11-18")
    summary = tracker.evaluate_live_trades([])
    assert summary.live_trades_count == 0
    assert summary.drift_status == "SAMPLE_BUILDING"
    assert summary.configured_base_risk_pct == 0.025


def test_live_forward_tracker_calculates_shortfall_and_slippage():
    tracker = LiveForwardTracker(parameter_freeze_date="2026-11-01")
    trades = []
    for idx in range(25):
        is_win = idx % 2 == 0
        trades.append(
            LiveTradeObservation(
                symbol="XRPUSDT",
                direction="LONG",
                closed_at=f"2026-11-{(idx % 20) + 2:02d}T12:00:00Z",
                signal_entry_price=1.0000,
                fill_entry_price=1.0003,  # +3.0 bps slippage
                risk_usd=20.0,
                gross_pnl_usd=28.0 if is_win else -13.0,
                fees_usd=0.60,
                funding_usd=0.20,
                theoretical_r=1.40 if is_win else -0.65,
            )
        )

    summary = tracker.evaluate_live_trades(trades)
    assert summary.live_trades_count == 25
    assert summary.win_rate_pct == 52.0
    assert summary.realized_profit_factor > 1.5
    assert summary.mean_entry_slippage_bps == 3.0
    assert summary.total_fees_and_funding_r > 0.0
    assert summary.implementation_shortfall_r < 0.0  # Fees + funding reducen el R neto vs teórico
    assert summary.drift_status == "IN_LINE"


def test_live_forward_tracker_detects_critical_degradation():
    tracker = LiveForwardTracker(parameter_freeze_date="2026-11-01")
    losing_trades = [
        LiveTradeObservation(
            symbol="SOLUSDT",
            direction="LONG",
            closed_at="2026-11-19T10:00:00Z",
            signal_entry_price=180.0,
            fill_entry_price=180.1,
            risk_usd=25.0,
            gross_pnl_usd=-20.0,
            fees_usd=0.5,
            funding_usd=0.1,
        )
        for _ in range(30)
    ]
    summary = tracker.evaluate_live_trades(losing_trades)
    assert summary.live_trades_count == 30
    assert summary.drift_z_score < -2.0
    assert summary.drift_status == "CRITICAL_DEGRADATION"
    assert summary.recommended_risk_action == "PAUSE_AUTO_EXECUTION_AND_AUDIT"


def test_enforce_policy_derisk_to_1pct_and_audit_log(tmp_path):
    import sqlite3
    from types import SimpleNamespace

    tracker = LiveForwardTracker(parameter_freeze_date="2026-11-01")
    # 25 trades con media ~ -0.05R -> z-score entre -1.5 y -2.0 (WARNING_DRIFT)
    mixed_trades = [
        LiveTradeObservation(
            symbol="ETHUSDT",
            direction="LONG",
            closed_at="2026-11-19T12:00:00Z",
            signal_entry_price=3000.0,
            fill_entry_price=3000.0,
            risk_usd=25.0,
            gross_pnl_usd=25.0 if i < 12 else -25.0,
        )
        for i in range(25)
    ]
    summary = tracker.evaluate_live_trades(mixed_trades)
    assert summary.drift_status == "WARNING_DRIFT"
    assert summary.recommended_risk_action == "DE_RISK_TO_1_0PCT"

    acc = SimpleNamespace(risk_pct=0.025)
    mgr = SimpleNamespace(_accounts={"primary": acc})
    db_file = str(tmp_path / "audit_derisk.db")

    result = tracker.apply_pre_registered_policy(
        summary, account_manager=mgr, audit_db_path=db_file
    )
    assert result["action_taken"] == "DE_RISK_TO_1_0PCT"
    assert acc.risk_pct == 0.010

    conn = sqlite3.connect(db_file)
    rows = conn.execute("SELECT action_taken, previous_risk_pct, new_risk_pct, paused FROM forward_policy_audit_log").fetchall()
    conn.close()
    assert len(rows) == 1
    assert rows[0] == ("DE_RISK_TO_1_0PCT", 0.025, 0.010, 0)


def test_enforce_policy_pause_and_override_immutable_audit_trail(tmp_path):
    import sqlite3

    tracker = LiveForwardTracker(parameter_freeze_date="2026-11-01")
    losing_trades = [
        LiveTradeObservation(
            symbol="SOLUSDT",
            direction="LONG",
            closed_at="2026-11-19T10:00:00Z",
            signal_entry_price=180.0,
            fill_entry_price=180.0,
            risk_usd=25.0,
            gross_pnl_usd=-20.0,
        )
        for _ in range(30)
    ]
    summary = tracker.evaluate_live_trades(losing_trades)
    db_file = str(tmp_path / "audit_pause.db")

    paused_flag = {"called": False}
    result = tracker.apply_pre_registered_policy(
        summary,
        pause_callback=lambda: paused_flag.__setitem__("called", True),
        audit_db_path=db_file,
    )
    assert result["action_taken"] == "PAUSE_AUTO_EXECUTION_AND_AUDIT"
    assert result["paused"] is True
    assert paused_flag["called"] is True

    # Intentar anular/override debe dejar registro inmutable en la misma tabla
    override_res = tracker.apply_pre_registered_policy(
        summary,
        audit_db_path=db_file,
        override_reason="Auditoria manual aprobada tras evento macro aislado",
    )
    assert override_res["action_taken"] == "POLICY_OVERRIDE_LOGGED"

    conn = sqlite3.connect(db_file)
    rows = conn.execute("SELECT action_taken, override_reason FROM forward_policy_audit_log ORDER BY id ASC").fetchall()
    conn.close()
    assert len(rows) == 2
    assert rows[0] == ("PAUSE_AUTO_EXECUTION_AND_AUDIT", None)
    assert rows[1] == ("POLICY_OVERRIDE_LOGGED", "Auditoria manual aprobada tras evento macro aislado")
