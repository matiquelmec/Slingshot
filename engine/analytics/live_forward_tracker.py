"""
engine/analytics/live_forward_tracker.py
========================================
TRACKER DE FORWARD-TEST EN VIVO & IMPLEMENTATION SHORTFALL (SOP-146)

Compara el rendimiento real fuera de muestra en Bitunix (operaciones cerradas en vivo
después de una fecha de congelamiento de parámetros `PARAMETER_FREEZE_DATE`) contra
la expectativa teórica del backtest ajustado por fricción (SOP-119):
  - Expectativa Real Neta en R (después de fees, funding y slippage real).
  - Implementation Shortfall (brecha entre retorno real y retorno teórico en R / bps).
  - Z-Score de Deriva Estadística (alerta si la desviación supera 2.0 errores estándar).
"""

import math
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from engine.core.strategy_ssot import (
    BITUNIX_CANONICAL_BASE_RISK_PCT,
    SOP119_MEAN_SL_SLIPPAGE_R,
)
from engine.analytics.quant_statistical_rigor import compute_wald_sprt

# Expectativa y desviación estándar de referencia del backtest 1R con fricción SOP-119
BENCHMARK_FRICTION_EXPECTANCY_R: float = 0.281
BENCHMARK_FRICTION_STD_R: float = 0.985
DEFAULT_PARAMETER_FREEZE_DATE: str = "2026-11-18"


@dataclass
class LiveTradeObservation:
    symbol: str
    direction: str
    closed_at: str
    signal_entry_price: float
    fill_entry_price: float
    risk_usd: float
    gross_pnl_usd: float
    fees_usd: float = 0.0
    funding_usd: float = 0.0
    theoretical_r: Optional[float] = None

    @property
    def net_pnl_usd(self) -> float:
        return float(self.gross_pnl_usd) - abs(float(self.fees_usd)) - float(self.funding_usd)

    @property
    def realized_net_r(self) -> float:
        if self.risk_usd <= 1e-9:
            return 0.0
        return round(self.net_pnl_usd / float(self.risk_usd), 4)

    @property
    def entry_slippage_bps(self) -> float:
        if self.signal_entry_price <= 1e-9:
            return 0.0
        dir_upper = str(self.direction or "LONG").upper()
        if "SHORT" in dir_upper:
            diff = self.signal_entry_price - self.fill_entry_price
        else:
            diff = self.fill_entry_price - self.signal_entry_price
        return round((diff / self.signal_entry_price) * 10000.0, 2)


@dataclass
class LiveForwardAuditSummary:
    parameter_freeze_date: str
    configured_base_risk_pct: float
    live_trades_count: int
    win_rate_pct: float
    realized_profit_factor: float
    realized_total_net_r: float
    realized_expectancy_r: float
    realized_std_r: float
    realized_ci95_low_r: float
    realized_ci95_high_r: float
    mean_entry_slippage_bps: float
    total_fees_and_funding_r: float
    benchmark_expectancy_r: float
    implementation_shortfall_r: float
    drift_z_score: float
    drift_status: str  # IN_LINE, SAMPLE_BUILDING, WARNING_DRIFT, CRITICAL_DEGRADATION
    recommended_risk_action: str = "KEEP_BASE_RISK_2_5PCT"  # Pre-registered de-risk policy
    sprt_log_likelihood: float = 0.0
    sprt_upper_bound: float = 2.8904
    sprt_lower_bound: float = -2.2513
    sprt_decision: str = "CONTINUE_SAMPLING"
    sprt_progress_pct: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class LiveForwardTracker:
    """
    Auditor cuantitativo de Forward-Test en vivo para validar la paridad entre el
    motor en producción (Bitunix) y la distribución de backtest con fricción SOP-119.
    """

    def __init__(
        self,
        parameter_freeze_date: str = DEFAULT_PARAMETER_FREEZE_DATE,
        benchmark_expectancy_r: float = BENCHMARK_FRICTION_EXPECTANCY_R,
        benchmark_std_r: float = BENCHMARK_FRICTION_STD_R,
    ):
        self.parameter_freeze_date = parameter_freeze_date
        self.benchmark_expectancy_r = benchmark_expectancy_r
        self.benchmark_std_r = benchmark_std_r

    def evaluate_live_trades(
        self, trades: List[LiveTradeObservation]
    ) -> LiveForwardAuditSummary:
        eligible = [
            t for t in trades if str(t.closed_at or "") >= self.parameter_freeze_date
        ]
        n = len(eligible)
        if n == 0:
            return LiveForwardAuditSummary(
                parameter_freeze_date=self.parameter_freeze_date,
                configured_base_risk_pct=BITUNIX_CANONICAL_BASE_RISK_PCT,
                live_trades_count=0,
                win_rate_pct=0.0,
                realized_profit_factor=0.0,
                realized_total_net_r=0.0,
                realized_expectancy_r=0.0,
                realized_std_r=0.0,
                realized_ci95_low_r=0.0,
                realized_ci95_high_r=0.0,
                mean_entry_slippage_bps=0.0,
                total_fees_and_funding_r=0.0,
                benchmark_expectancy_r=self.benchmark_expectancy_r,
                implementation_shortfall_r=0.0,
                drift_z_score=0.0,
                drift_status="SAMPLE_BUILDING",
            )

        net_rs = np.array([t.realized_net_r for t in eligible], dtype=np.float64)
        winners = net_rs[net_rs > 0]
        losers = net_rs[net_rs < 0]

        win_rate = float(len(winners) / n) * 100.0
        gp = float(np.sum(winners)) if len(winners) > 0 else 0.0
        gl = float(np.abs(np.sum(losers))) if len(losers) > 0 else 0.0
        pf = (gp / gl) if gl > 1e-9 else (99.0 if gp > 0 else 0.0)

        total_r = float(np.sum(net_rs))
        mean_r = float(np.mean(net_rs))
        std_r = float(np.std(net_rs, ddof=1)) if n > 1 else self.benchmark_std_r
        se_r = (std_r / math.sqrt(n)) if n > 1 else self.benchmark_std_r
        ci95_low = mean_r - 1.96 * se_r
        ci95_high = mean_r + 1.96 * se_r

        slippages = [t.entry_slippage_bps for t in eligible]
        mean_slip_bps = float(np.mean(slippages)) if slippages else 0.0

        fee_drag_r_list = [
            ((abs(t.fees_usd) + t.funding_usd) / t.risk_usd)
            for t in eligible
            if t.risk_usd > 1e-9
        ]
        total_fee_drag_r = float(np.sum(fee_drag_r_list)) if fee_drag_r_list else 0.0

        # Implementation Shortfall respecto al benchmark teórico con o sin theoretical_r por trade
        theo_refs = [
            float(t.theoretical_r)
            for t in eligible
            if t.theoretical_r is not None
        ]
        ref_expectancy = (
            float(np.mean(theo_refs)) if len(theo_refs) == n else self.benchmark_expectancy_r
        )
        shortfall_r = round(mean_r - ref_expectancy, 4)

        ref_se = self.benchmark_std_r / math.sqrt(n)
        z_score = round((mean_r - self.benchmark_expectancy_r) / ref_se, 3) if ref_se > 1e-9 else 0.0

        if n < 20:
            status = "SAMPLE_BUILDING"
            risk_action = "KEEP_BASE_RISK_2_5PCT"
        elif z_score <= -2.0:
            status = "CRITICAL_DEGRADATION"
            risk_action = "PAUSE_AUTO_EXECUTION_AND_AUDIT"
        elif z_score <= -1.5:
            status = "WARNING_DRIFT"
            risk_action = "DE_RISK_TO_1_0PCT"
        else:
            status = "IN_LINE"
            risk_action = "KEEP_BASE_RISK_2_5PCT"

        sprt = compute_wald_sprt(net_rs.tolist(), mu0=0.0, mu1=0.25, sigma=self.benchmark_std_r)

        return LiveForwardAuditSummary(
            parameter_freeze_date=self.parameter_freeze_date,
            configured_base_risk_pct=BITUNIX_CANONICAL_BASE_RISK_PCT,
            live_trades_count=n,
            win_rate_pct=round(win_rate, 2),
            realized_profit_factor=round(pf, 2),
            realized_total_net_r=round(total_r, 3),
            realized_expectancy_r=round(mean_r, 3),
            realized_std_r=round(std_r, 3),
            realized_ci95_low_r=round(ci95_low, 3),
            realized_ci95_high_r=round(ci95_high, 3),
            mean_entry_slippage_bps=round(mean_slip_bps, 2),
            total_fees_and_funding_r=round(total_fee_drag_r, 3),
            benchmark_expectancy_r=round(ref_expectancy, 3),
            implementation_shortfall_r=shortfall_r,
            drift_z_score=z_score,
            drift_status=status,
            recommended_risk_action=risk_action,
            sprt_log_likelihood=sprt["sprt_log_likelihood"],
            sprt_upper_bound=sprt["sprt_upper_bound"],
            sprt_lower_bound=sprt["sprt_lower_bound"],
            sprt_decision=sprt["sprt_decision"],
            sprt_progress_pct=sprt["sprt_progress_pct"],
        )

    def apply_pre_registered_policy(
        self,
        summary: LiveForwardAuditSummary,
        account_manager: Optional[Any] = None,
        pause_callback: Optional[Callable[[], Any]] = None,
        audit_db_path: str = "slingshot_vault.db",
        override_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Ejecuta la política pre-comprometida de degradación y registra cada acción
        (o intento de anulación/override) en una tabla append-only `forward_policy_audit_log`
        en SQLite WAL para garantizar trazabilidad inmutable.
        """
        action = summary.recommended_risk_action
        prev_risk = summary.configured_base_risk_pct
        new_risk = prev_risk
        paused = False
        action_taken = "NO_CHANGE"

        if override_reason and override_reason.strip():
            action_taken = "POLICY_OVERRIDE_LOGGED"
        elif action == "DE_RISK_TO_1_0PCT":
            new_risk = 0.010
            action_taken = "DE_RISK_TO_1_0PCT"
            if account_manager is not None:
                accounts = getattr(account_manager, "_accounts", {}) or {}
                for acc in accounts.values():
                    if hasattr(acc, "risk_pct"):
                        acc.risk_pct = 0.010
        elif action == "PAUSE_AUTO_EXECUTION_AND_AUDIT":
            paused = True
            action_taken = "PAUSE_AUTO_EXECUTION_AND_AUDIT"
            if pause_callback is not None:
                pause_callback()

        ts_utc = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(audit_db_path)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS forward_policy_audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp_utc TEXT NOT NULL,
                    parameter_freeze_date TEXT NOT NULL,
                    live_trades_count INTEGER NOT NULL,
                    drift_z_score REAL NOT NULL,
                    drift_status TEXT NOT NULL,
                    action_taken TEXT NOT NULL,
                    previous_risk_pct REAL NOT NULL,
                    new_risk_pct REAL NOT NULL,
                    paused INTEGER NOT NULL,
                    override_reason TEXT
                )
                """
            )
            conn.execute(
                """
                INSERT INTO forward_policy_audit_log (
                    timestamp_utc, parameter_freeze_date, live_trades_count,
                    drift_z_score, drift_status, action_taken,
                    previous_risk_pct, new_risk_pct, paused, override_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ts_utc,
                    summary.parameter_freeze_date,
                    int(summary.live_trades_count),
                    float(summary.drift_z_score),
                    summary.drift_status,
                    action_taken,
                    float(prev_risk),
                    float(new_risk),
                    1 if paused else 0,
                    override_reason.strip() if override_reason else None,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        return {
            "timestamp_utc": ts_utc,
            "action_taken": action_taken,
            "previous_risk_pct": prev_risk,
            "new_risk_pct": new_risk,
            "paused": paused,
            "override_reason": override_reason.strip() if override_reason else None,
        }
