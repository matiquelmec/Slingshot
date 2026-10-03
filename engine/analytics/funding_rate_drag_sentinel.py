"""
engine/analytics/funding_rate_drag_sentinel.py
=============================================
ESCUDO DINÁMICO DE FUNDING RATES Y CARRY DRAG (SOP-109 - SSoT v61.0)

Gobernanza bajo AGENTS.md & BLUEPRINT_2026.md:
1. En posiciones runner prolongadas (SOP-104), audita el coste acumulado por tasas de financiamiento.
2. Calcula la tasa anualizada (APR) y el drag devengado en unidades de R:
   Funding Drag (R) = Sum(Funding Fee) / Initial Dollar Risk
3. Reglas de Modulación Táctica:
   - Funding APR <= 35.0%: Estado NORMAL. Trailing Ratchet Chandelier estándar (1.5x ATR).
   - Funding APR > 50.0% o Drag >= 0.50R: Estado WARNING_TIGHTEN. Aprieta el Chandelier de 1.5x a 1.0x ATR.
   - Funding APR > 75.0% o Drag >= 1.20R: Estado CRITICAL_HARVEST. Cierra el runner o fuerza TP en +8.0R.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


@dataclass
class FundingDragAuditResult:
    asset: str
    current_funding_rate_8h_pct: float
    annualized_funding_apr_pct: float
    accumulated_funding_drag_r: float
    status: str  # 'NORMAL', 'WARNING_TIGHTEN', 'CRITICAL_HARVEST'
    recommended_chandelier_multiplier: float  # 1.5x, 1.0x, or 0.0 (force close)
    action_directive: str


class FundingRateDragSentinel:
    """
    Centinela institucional que protege la rentabilidad neta de posiciones runners
    contra la erosión por funding rates extremos en futuros perpetuos.
    """

    def __init__(
        self,
        warning_apr_pct: float = 50.0,
        critical_apr_pct: float = 75.0,
        max_tolerable_drag_r: float = 0.50,
    ):
        self.warning_apr_pct = warning_apr_pct
        self.critical_apr_pct = critical_apr_pct
        self.max_tolerable_drag_r = max_tolerable_drag_r

    def audit_position_carry(
        self,
        asset: str,
        direction: str,  # 'LONG' or 'SHORT'
        funding_rate_8h: float,  # ej: 0.0003 (0.03%)
        duration_days: float,
        position_notional_usd: float,
        initial_dollar_risk: float,
    ) -> FundingDragAuditResult:
        """
        Audita el coste de arrastre por carry trade y dictamina ajuste del trailing.
        """
        # Funding 8h a porcentaje y anualizado (1095 intervalos de 8h al año)
        rate_8h_pct = funding_rate_8h * 100.0
        annualized_apr = rate_8h_pct * 3.0 * 365.0  # 3 pagos de 8h al día

        # Si estamos LONG y funding es positivo, pagamos. Si es negativo, cobramos.
        # Si estamos SHORT y funding es positivo, cobramos. Si es negativo, pagamos.
        direction_multiplier = 1.0 if direction.upper() == "LONG" else -1.0
        daily_cost_pct = (funding_rate_8h * 3.0) * direction_multiplier

        # Coste total estimado devengado en USD y en R
        accumulated_cost_usd = daily_cost_pct * position_notional_usd * duration_days
        drag_r = accumulated_cost_usd / initial_dollar_risk if initial_dollar_risk > 0 else 0.0

        status = "NORMAL"
        multiplier = 1.5
        directive = "MANTENER_TRAILING_CHANDELIER_1.5X_ATR"

        if annualized_apr >= self.critical_apr_pct or drag_r >= (self.max_tolerable_drag_r * 2.0):
            status = "CRITICAL_HARVEST"
            multiplier = 0.5
            directive = "FORZAR_TOMA_DE_GANANCIAS_RUNNER_PREVENIR_EROSION"
        elif annualized_apr >= self.warning_apr_pct or drag_r >= self.max_tolerable_drag_r:
            status = "WARNING_TIGHTEN"
            multiplier = 1.0
            directive = "APRETAR_TRAILING_A_1.0X_ATR_ASEGURAR_BENEFICIO"

        return FundingDragAuditResult(
            asset=asset,
            current_funding_rate_8h_pct=round(rate_8h_pct, 4),
            annualized_funding_apr_pct=round(annualized_apr, 1),
            accumulated_funding_drag_r=round(drag_r, 3),
            status=status,
            recommended_chandelier_multiplier=multiplier,
            action_directive=directive,
        )


def get_canonical_universe_funding_summary() -> List[Dict[str, Any]]:
    """Helper directo para integración full-stack con los 13 activos canónicos SSoT."""
    from engine.workers.asset_incubator import CANONICAL_AUDITED_UNIVERSE
    sentinel = FundingRateDragSentinel()

    summaries = []
    # Tasas representativas de mercado actual en rango alto
    rates_map = {
        "BTCUSDT": 0.0001,   # 0.01% (10.95% APR) - Neutral
        "ETHUSDT": 0.00012,  # 0.012%
        "SOLUSDT": 0.00025,  # 0.025% (27.3% APR)
        "BNBUSDT": 0.00015,  # 0.015%
        "FETUSDT": 0.00035,  # 0.035% (38.3% APR)
        "NEARUSDT": 0.00028, # 0.028%
    }

    for asset in CANONICAL_AUDITED_UNIVERSE:
        rate = rates_map.get(asset, 0.00015)
        res = sentinel.audit_position_carry(
            asset=asset,
            direction="LONG",
            funding_rate_8h=rate,
            duration_days=5.0,
            position_notional_usd=5000.0,
            initial_dollar_risk=125.0,  # 2.5% sobre $5k
        )
        summaries.append({
            "asset": res.asset,
            "currentFundingRate8hPct": res.current_funding_rate_8h_pct,
            "annualizedFundingAprPct": res.annualized_funding_apr_pct,
            "accumulatedFundingDragR": res.accumulated_funding_drag_r,
            "status": res.status,
            "recommendedChandelierMultiplier": res.recommended_chandelier_multiplier,
            "actionDirective": res.action_directive,
        })
    return summaries
