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
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

import numpy as np

from engine.core.strategy_ssot import (
    BITUNIX_CANONICAL_BASE_RISK_PCT,
    SOP119_MEAN_SL_SLIPPAGE_R,
)

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
        elif z_score <= -2.0:
            status = "CRITICAL_DEGRADATION"
        elif z_score <= -1.25:
            status = "WARNING_DRIFT"
        else:
            status = "IN_LINE"

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
        )
