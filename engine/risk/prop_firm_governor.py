"""
engine/risk/prop_firm_governor.py — Prop-Firm Apex Governor (SOP-151)
=======================================================================
Gobernanza institucional aislada para cuentas de fondeo (FTMO Swing / Crypto Prop Firms):
1. Prop-Firm Tier-1 Universe: concentra la operativa en los 8 pares con mayor liquidez L2,
   menor spread (< 1.5 bps) y ventaja estadística auditada.
2. Core-to-MT5 Bridge Map: traduce señales del Core SMC (BTCUSDT, ETHUSDT, SOLUSDT, XAUUSDT)
   a símbolos nativos de MetaTrader 5 (BTCUSD, ETHUSD, SOLUSD, XAUUSD).
3. Near-Target Risk Dampener: reduce 50% el riesgo por trade al superar el 85% de la meta.
4. Consistency Daily Cap: evita concentrar más del % permitido de la meta en un solo día.
"""

from typing import Dict, Optional, Tuple

PROP_FIRM_TIER1_CRYPTO_UNIVERSE = (
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "XAUUSDT",
    "NEARUSDT",
    "BTCUSDT",
    "XRPUSDT",
    "LINKUSDT",
)

FTMO_MT5_BRIDGE_MAP: Dict[str, str] = {
    "BTCUSDT": "BTCUSD",
    "ETHUSDT": "ETHUSD",
    "SOLUSDT": "SOLUSD",
    "XAUUSDT": "XAUUSD",
}


class PropFirmGovernor:
    """Gobernador de riesgo y elegibilidad de activos para pruebas de fondeo."""

    def __init__(
        self,
        min_trading_days: int = 4,
        near_target_threshold_pct: float = 85.0,
        max_daily_profit_share_pct: Optional[float] = None,
    ):
        self.min_trading_days = min_trading_days
        self.near_target_threshold_pct = near_target_threshold_pct
        self.max_daily_profit_share_pct = max_daily_profit_share_pct

    @staticmethod
    def is_prop_tier1_asset(symbol: str) -> bool:
        clean = (symbol or "").replace("/", "").replace(" ", "").upper()
        return clean in PROP_FIRM_TIER1_CRYPTO_UNIVERSE

    @staticmethod
    def map_core_to_mt5_symbol(symbol: str) -> Optional[str]:
        clean = (symbol or "").replace("/", "").replace(" ", "").upper()
        return FTMO_MT5_BRIDGE_MAP.get(clean)

    def compute_prop_adjusted_risk_pct(
        self,
        base_risk_pct: float,
        progress_pct: float,
        daily_profit_pct: float = 0.0,
        target_pct: float = 10.0,
    ) -> Tuple[float, str]:
        """
        Calcula el riesgo ajustado para cuentas de fondeo (sin Mega-Kelly):
        - Si existe Consistency Cap y la ganancia del día alcanzó el tope, retorna 0.0.
        - Si el progreso supera el 85% de la meta (Near-Target Dampener), reduce el riesgo a la mitad.
        """
        if (
            self.max_daily_profit_share_pct is not None
            and target_pct > 0
            and daily_profit_pct > 0
        ):
            daily_cap_pct = target_pct * (self.max_daily_profit_share_pct / 100.0)
            if daily_profit_pct >= daily_cap_pct:
                return 0.0, f"CONSISTENCY_CAP_REACHED ({daily_profit_pct:.2f}% >= {daily_cap_pct:.2f}%)"

        if progress_pct >= self.near_target_threshold_pct and target_pct > 0:
            dampened = round(base_risk_pct * 0.5, 5)
            return dampened, f"NEAR_TARGET_DAMPENER ({progress_pct:.1f}% >= {self.near_target_threshold_pct:.0f}%)"

        return base_risk_pct, "STANDARD_PROP_RISK"


prop_firm_governor = PropFirmGovernor()
