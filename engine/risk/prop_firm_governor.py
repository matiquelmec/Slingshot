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

# [SOP-152] Matriz validada en Torneo Walk-Forward ciego (60% Train / 40% Blind OOS)
CRYPTO_PROP_APPROVED_MATRIX: Dict[str, str] = {
    "ETHUSDT": "15m",
    "BNBUSDT": "15m",
    "SOLUSDT": "15m",
    "XAUUSDT": "1h",
    "NEARUSDT": "15m",
    "BTCUSDT": "1h",
    "XRPUSDT": "15m",
    "LINKUSDT": "15m",
    "DOTUSDT": "15m",
}

# [SOP-154] Matriz FTMO Swing validada en Torneo Walk-Forward ciego (60% Train / 40% Blind OOS)
FTMO_MT5_APPROVED_MATRIX: Dict[str, Dict[str, str]] = {
    "XAUUSD": {"timeframe": "1h", "archetype": "IMPULSE_OTE_SMC", "cluster": "SAFE_HAVEN_METALS"},
    "US100":  {"timeframe": "1h", "archetype": "IMPULSE_OTE_SMC", "cluster": "US_EQUITY_INDICES"},
    "XAGUSD": {"timeframe": "1h", "archetype": "IMPULSE_OTE_SMC", "cluster": "SAFE_HAVEN_METALS"},
    "UK100":  {"timeframe": "1h", "archetype": "LIQUIDITY_SWEEP_JUDAS", "cluster": "GLOBAL_EQUITY_INDICES"},
}

MACRO_CLUSTER_MAP: Dict[str, str] = {
    "BTCUSDT": "CRYPTO_BETA", "ETHUSDT": "CRYPTO_BETA", "SOLUSDT": "CRYPTO_BETA",
    "BNBUSDT": "CRYPTO_BETA", "XRPUSDT": "CRYPTO_BETA", "LINKUSDT": "CRYPTO_BETA",
    "NEARUSDT": "CRYPTO_BETA", "DOTUSDT": "CRYPTO_BETA",
    "XAUUSDT": "SAFE_HAVEN_METALS", "XAUUSD": "SAFE_HAVEN_METALS", "XAGUSD": "SAFE_HAVEN_METALS",
    "US100": "US_EQUITY_INDICES", "US500": "US_EQUITY_INDICES", "US30": "US_EQUITY_INDICES", "US2000": "US_EQUITY_INDICES",
    "GER40": "GLOBAL_EQUITY_INDICES", "UK100": "GLOBAL_EQUITY_INDICES", "JP225": "GLOBAL_EQUITY_INDICES", "EU50": "GLOBAL_EQUITY_INDICES",
    "USOIL": "INDUSTRIAL_ENERGY", "UKOIL": "INDUSTRIAL_ENERGY", "HGUSD": "INDUSTRIAL_ENERGY",
    "EURUSD": "G10_FX_USD", "GBPUSD": "G10_FX_USD", "USDJPY": "G10_FX_USD", "USDCAD": "G10_FX_USD",
    "AUDUSD": "G10_FX_USD", "USDCHF": "G10_FX_USD", "NZDUSD": "G10_FX_USD",
    "EURJPY": "G10_FX_CROSS", "GBPJPY": "G10_FX_CROSS", "EURGBP": "G10_FX_CROSS",
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

    @staticmethod
    def is_spread_to_risk_acceptable(
        entry_price: float,
        stop_loss: float,
        round_trip_cost_usd: float,
        max_ratio: float = 0.08,
    ) -> Tuple[bool, float]:
        """
        [SOP-152A] Rechaza entradas cuyo costo (spread + comisión) supere el 8% de |Entry - SL|.
        """
        risk_dist = abs(float(entry_price) - float(stop_loss))
        if risk_dist <= 1e-9:
            return False, 1.0
        ratio = float(round_trip_cost_usd) / risk_dist
        return ratio <= max_ratio, round(ratio, 4)

    @staticmethod
    def is_cluster_slot_available(
        symbol: str,
        open_unsecured_symbols: list,
    ) -> Tuple[bool, str]:
        """
        [SOP-152B] Máximo 1 posición con riesgo abierto (SL != BE) por clúster macro.
        """
        clean = (symbol or "").replace("/", "").replace(".cash", "").upper()
        target_cluster = MACRO_CLUSTER_MAP.get(clean, "OTHER")
        for op_sym in open_unsecured_symbols:
            op_clean = (op_sym or "").replace("/", "").replace(".cash", "").upper()
            if MACRO_CLUSTER_MAP.get(op_clean, "OTHER") == target_cluster:
                return False, f"CLUSTER_CAP_ACTIVE ({target_cluster}: {op_clean})"
        return True, target_cluster


prop_firm_governor = PropFirmGovernor()
