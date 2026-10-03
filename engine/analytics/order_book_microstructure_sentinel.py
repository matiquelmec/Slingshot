"""
engine/analytics/order_book_microstructure_sentinel.py
======================================================
CENTINELA DE MICROESTRUCTURA Y LIBRO DE ÓRDENES L2 (SOP-108 - SSoT v61.0)

Gobernanza bajo AGENTS.md & BLUEPRINT_2026.md:
1. Audita la profundidad del libro de órdenes L2 (bids y asks hasta 20 niveles)
   antes de colocar órdenes límite en Order Blocks u OTE.
2. Calcula el Order Book Imbalance (OBI) normalizado en [-1.0, +1.0]:
   OBI = (Sum Q_bid - Sum Q_ask) / (Sum Q_bid + Sum Q_ask)
3. Detecta muros de manipulación ficticia (spoofing) y ensanchamiento anormal de spreads.
4. Reglas de Veto Institucional:
   - Para LONG: Requiere OBI >= -0.25. Si OBI < -0.35 (fuerte presión vendedora pasiva), veta la entrada.
   - Para SHORT: Requiere OBI <= +0.25. Si OBI > +0.35, veta la entrada.
   - Spread relativo máximo permitido: 0.08% (8 bps). Spreads mayores activan veto por iliquidez.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
import numpy as np


@dataclass
class OrderBookLevel:
    price: float
    quantity: float


@dataclass
class MicrostructureAuditResult:
    asset: str
    is_approved: boolean if False else bool  # typing bool
    veto_reason: Optional[str]
    obi_score: float  # [-1.0, 1.0]
    effective_spread_bps: float
    bid_depth_usd: float
    ask_depth_usd: float
    mid_price: float
    spoofing_detected: bool
    recommended_action: str


class OrderBookMicrostructureSentinel:
    """
    Centinela institucional que audita la liquidez L2 y el desbalance del libro.
    """

    def __init__(
        self,
        max_spread_bps: float = 8.0,      # 0.08% máximo
        min_long_obi: float = -0.25,      # Umbral para compras
        max_short_obi: float = 0.25,      # Umbral para ventas
        min_depth_usd: float = 50000.0,   # Mínimo $50k en los 20 niveles
    ):
        self.max_spread_bps = max_spread_bps
        self.min_long_obi = min_long_obi
        self.max_short_obi = max_short_obi
        self.min_depth_usd = min_depth_usd

    def audit_l2_book(
        self,
        asset: str,
        direction: str,  # 'LONG' o 'SHORT'
        bids: List[Tuple[float, float]],  # List of (price, qty)
        asks: List[Tuple[float, float]],  # List of (price, qty)
        max_levels: int = 20,
    ) -> MicrostructureAuditResult:
        """
        Audita el snapshot L2 y dictamina aprobación o veto preventivo.
        """
        if not bids or not asks:
            return MicrostructureAuditResult(
                asset=asset,
                is_approved=False,
                veto_reason="LIBRO_L2_VACIO: No se recibieron datos de bids o asks del exchange.",
                obi_score=0.0,
                effective_spread_bps=999.0,
                bid_depth_usd=0.0,
                ask_depth_usd=0.0,
                mid_price=0.0,
                spoofing_detected=False,
                recommended_action="ABORT_ENTRY",
            )

        # Truncar a los mejores max_levels
        bids_slice = bids[:max_levels]
        asks_slice = asks[:max_levels]

        best_bid = float(bids_slice[0][0])
        best_ask = float(asks_slice[0][0])

        if best_bid >= best_ask:
            return MicrostructureAuditResult(
                asset=asset,
                is_approved=False,
                veto_reason="LIBRO_INVERTIDO_CROSSED: Best bid >= Best ask en snapshot L2.",
                obi_score=0.0,
                effective_spread_bps=0.0,
                bid_depth_usd=0.0,
                ask_depth_usd=0.0,
                mid_price=best_bid,
                spoofing_detected=True,
                recommended_action="ABORT_ENTRY",
            )

        mid_price = (best_bid + best_ask) / 2.0
        spread_bps = ((best_ask - best_bid) / mid_price) * 10000.0

        # Volumen nocional en USD
        bid_vol_usd = sum(float(p) * float(q) for p, q in bids_slice)
        ask_vol_usd = sum(float(p) * float(q) for p, q in asks_slice)
        total_vol = bid_vol_usd + ask_vol_usd

        # Cálculo de OBI (Order Book Imbalance)
        obi = (bid_vol_usd - ask_vol_usd) / total_vol if total_vol > 0 else 0.0

        # Detección de Spoofing / Anomalía de concentración (si un solo nivel tiene > 65% de todo el volumen)
        spoofing = False
        max_single_bid = max(float(p) * float(q) for p, q in bids_slice) if bids_slice else 0
        max_single_ask = max(float(p) * float(q) for p, q in asks_slice) if asks_slice else 0
        if (bid_vol_usd > 0 and max_single_bid / bid_vol_usd > 0.65) or (
            ask_vol_usd > 0 and max_single_ask / ask_vol_usd > 0.65
        ):
            spoofing = True

        # Reglas de Veto
        veto_reason = None
        is_approved = True

        if spread_bps > self.max_spread_bps:
            is_approved = False
            veto_reason = f"SPREAD_EXCESIVO: {spread_bps:.1f} bps supera el límite de {self.max_spread_bps:.1f} bps."

        elif direction.upper() == "LONG" and obi < self.min_long_obi:
            is_approved = False
            veto_reason = f"OBI_VENTA_DOMINANTE: OBI {obi:.2f} inferior al umbral mínimo {self.min_long_obi:.2f}."

        elif direction.upper() == "SHORT" and obi > self.max_short_obi:
            is_approved = False
            veto_reason = f"OBI_COMPRA_DOMINANTE: OBI {obi:.2f} superior al umbral máximo {self.max_short_obi:.2f}."

        elif total_vol < self.min_depth_usd:
            is_approved = False
            veto_reason = f"LIQUIDEZ_INSUFICIENTE: Profundidad total ${total_vol:,.0f} inferior a ${self.min_depth_usd:,.0f}."

        recommended_action = "PROCEED_ORDER_DISPATCH" if is_approved else "HOLD_IN_SELECTIVE_PATIENCE"

        return MicrostructureAuditResult(
            asset=asset,
            is_approved=is_approved,
            veto_reason=veto_reason,
            obi_score=round(obi, 3),
            effective_spread_bps=round(spread_bps, 2),
            bid_depth_usd=round(bid_vol_usd, 2),
            ask_depth_usd=round(ask_vol_usd, 2),
            mid_price=round(mid_price, 4),
            spoofing_detected=spoofing,
            recommended_action=recommended_action,
        )


def get_canonical_universe_l2_summary() -> List[Dict[str, Any]]:
    """Helper que provee auditoría L2 sintética para los 13 activos canónicos SSoT."""
    from engine.workers.asset_incubator import CANONICAL_AUDITED_UNIVERSE
    sentinel = OrderBookMicrostructureSentinel()

    summaries = []
    for asset in CANONICAL_AUDITED_UNIVERSE:
        # Generación determinista calibrada según liquidez institucional auditada
        if "BTC" in asset:
            bids = [(84600.0 - i * 5, 2.5 + i * 0.2) for i in range(20)]
            asks = [(84601.5 + i * 5, 2.3 + i * 0.2) for i in range(20)]
        elif "ETH" in asset:
            bids = [(3450.0 - i * 0.5, 15.0 + i * 1.5) for i in range(20)]
            asks = [(3450.2 + i * 0.5, 14.2 + i * 1.2) for i in range(20)]
        elif "SOL" in asset or "BNB" in asset or "FET" in asset:
            bids = [(180.0 - i * 0.1, 120.0 + i * 10) for i in range(20)]
            asks = [(180.03 + i * 0.1, 100.0 + i * 8) for i in range(20)]
        else:
            bids = [(10.0 - i * 0.01, 800.0 + i * 50) for i in range(20)]
            asks = [(10.005 + i * 0.01, 750.0 + i * 45) for i in range(20)]

        res = sentinel.audit_l2_book(asset, "LONG", bids, asks)
        summaries.append({
            "asset": res.asset,
            "isApproved": res.is_approved,
            "vetoReason": res.veto_reason,
            "obiScore": res.obi_score,
            "effectiveSpreadBps": res.effective_spread_bps,
            "bidDepthUsd": res.bid_depth_usd,
            "askDepthUsd": res.ask_depth_usd,
            "midPrice": res.mid_price,
            "spoofingDetected": res.spoofing_detected,
            "recommendedAction": res.recommended_action,
        })
    return summaries
