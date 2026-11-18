"""
engine/core/strategy_ssot.py
============================
SINGLE SOURCE OF TRUTH (SSoT) DE GOBERNANZA ESTRATÉGICA — SLINGSHOT TRADING

Centraliza todas las reglas cuantitativas, matrices de activos aprobados por
temporalidad, guardias direccionales (SOP-137), horas tóxicas, límites de
concurrencia (SOP-97 / SOP-99), scoring de prioridad y parámetros de fricción
empírica en vivo (SOP-119) para garantizar paridad 1:1 entre:
  - MarketScanner (detección y filtrado en vivo)
  - NexusNode (cola de prioridad y cupos)
  - UnifiedBacktestEngine (replay cronológico)
  - MonteCarloResilienceEngine (auditoría estocástica)
"""

from typing import FrozenSet, Optional, Tuple

# =============================================================================
# 1. UNIVERSO CANÓNICO Y MATRIZ ACTIVO:TIMEFRAME (SOP-125 & SOP-139)
# =============================================================================
CANONICAL_AUDITED_UNIVERSE: FrozenSet[str] = frozenset({
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "SUIUSDT", "INJUSDT", "NEARUSDT", "FETUSDT", "ATOMUSDT",
    "TIAUSDT", "LINKUSDT", "XAUUSDT",
})

PRUNED_NEGATIVE_EXPECTANCY_ASSETS: FrozenSet[str] = frozenset({
    "AVAXUSDT", "RENDERUSDT",
})

APPROVED_SCALP_15M_EXECUTION: FrozenSet[str] = frozenset({
    "BNBUSDT", "ETHUSDT", "SOLUSDT", "NEARUSDT",
    "FETUSDT", "INJUSDT", "ATOMUSDT", "XRPUSDT",
})

APPROVED_SWING_1H_EXECUTION: FrozenSet[str] = frozenset({
    "XAUUSDT", "BTCUSDT", "NEARUSDT", "ATOMUSDT",
    "ETHUSDT", "LINKUSDT",
})

# =============================================================================
# 2. GUARDIA DIRECCIONAL ASIMÉTRICA Y QUIRÓFANO HORARIO (SOP-137)
# =============================================================================
SHORT_ONLY_ASYMMETRIC_ASSETS_SOP137: FrozenSet[str] = frozenset({
    "INJUSDT", "LINKUSDT",
})

LONG_ONLY_STRUCTURAL_ASSETS_SOP137: FrozenSet[str] = frozenset({
    "XAUUSDT", "XAUUSD", "SOLUSDT", "SUIUSDT",
})

TOXIC_UTC_HOURS_SOP137: FrozenSet[int] = frozenset({7, 10, 14, 21, 22})

# =============================================================================
# 3. CONCURRENCIA Y ELASTICIDAD DE CUPOS (SOP-97 & SOP-99)
# =============================================================================
BASE_MAX_UNPROTECTED_RISK_SLOTS: int = 2
BASE_MAX_CONCURRENT_PHYSICAL_SLOTS: int = 4

ELASTIC_MAX_UNPROTECTED_RISK_SLOTS: int = 3
ELASTIC_MAX_CONCURRENT_PHYSICAL_SLOTS: int = 5

STREAK_CONTRACTION_UNPROTECTED_SLOTS: int = 1
STREAK_CONTRACTION_PHYSICAL_SLOTS: int = 3

# =============================================================================
# 4. SCORING DE PRIORIDAD ALPHA-TIER (SOP-97 & SOP-137)
# =============================================================================
PRIORITY_BOOST_TIER_1_25X: Tuple[str, ...] = ("ETH", "SOL", "BNB", "INJ", "FET", "XAU")
PRIORITY_BOOST_TIER_1_00X: Tuple[str, ...] = ("AVAX", "NEAR", "SUI", "XRP", "BTC", "ATOM")
PRIORITY_TIER_1_MULTIPLIER: float = 1.25
PRIORITY_TIER_2_MULTIPLIER: float = 1.00
PRIORITY_TIER_3_MULTIPLIER: float = 0.85

# =============================================================================
# 5. PARÁMETROS DE FRICCIÓN EMPÍRICA EN VIVO (SOP-119)
# =============================================================================
SOP119_LIVE_HAIRCUT_FACTOR: float = 0.884  # ~11.6% degradación por fricción real
SOP119_MAKER_FILL_RATE: float = 0.962      # 96.2% tasa de llenado límite
SOP119_MEAN_SL_SLIPPAGE_R: float = 0.04    # 0.03R - 0.08R slippage medio en SL


def normalize_symbol(symbol: str) -> str:
    """Normaliza símbolos eliminando '/' y asegurando sufijo USDT salvo oro."""
    sym = (symbol or "").replace("/", "").upper()
    if sym and not sym.endswith("USDT") and sym not in ("XAUUSD", "XAUUSDT"):
        sym = f"{sym}USDT"
    return sym


def is_quant_approved_pair(symbol: str, interval: str) -> bool:
    """Verifica si el par Activo:Timeframe supera los umbrales SSoT (SOP-125 / SOP-139)."""
    sym = normalize_symbol(symbol)
    if sym in PRUNED_NEGATIVE_EXPECTANCY_ASSETS:
        return False
    tf = (interval or "15m").lower()
    if tf == "15m":
        return sym in APPROVED_SCALP_15M_EXECUTION
    if tf == "1h":
        return sym in APPROVED_SWING_1H_EXECUTION
    return True


def is_directional_setup_allowed_sop137(
    symbol: str,
    direction: str,
    rs_zscore_vs_btc: Optional[float] = None,
    obi_score: Optional[float] = None,
) -> bool:
    """
    [SOP-137 + SOP-142] Gobernanza direccional híbrida:
    - Sin telemetría viva: aplica el prior estático auditado (SOP-137).
    - Con telemetría viva (rs_zscore_vs_btc / obi_score): permite override por
      ruptura institucional (>= +1.5σ para LONG, <= -1.5σ para SHORT) y veta
      entradas contra fuerza relativa extrema (>= ±1.8σ).
    """
    sym = normalize_symbol(symbol)
    dir_clean = "SHORT" if "SHORT" in str(direction or "LONG").upper() else "LONG"

    if rs_zscore_vs_btc is not None:
        rs_z = float(rs_zscore_vs_btc)
        if dir_clean == "LONG" and rs_z <= -1.8:
            return False
        if dir_clean == "SHORT" and rs_z >= 1.8:
            return False
        if dir_clean == "LONG" and rs_z >= 1.5 and (obi_score is None or float(obi_score) >= 0.20):
            return True
        if dir_clean == "SHORT" and rs_z <= -1.5 and (obi_score is None or float(obi_score) <= -0.20):
            return True

    if sym in SHORT_ONLY_ASYMMETRIC_ASSETS_SOP137 and dir_clean == "LONG":
        return False
    if sym in LONG_ONLY_STRUCTURAL_ASSETS_SOP137 and dir_clean == "SHORT":
        return False
    return True


def is_toxic_hour_sop137(
    hour_utc: int,
    spread_bps: Optional[float] = None,
    obi_score: Optional[float] = None,
    ker: Optional[float] = None,
    depth_usd: Optional[float] = None,
) -> bool:
    """
    [SOP-137 + SOP-142] Evalúa toxicidad horaria:
    - Sin telemetría L2: usa el calendario estático TOXIC_UTC_HOURS_SOP137.
    - Con telemetría L2: desbloquea horas si la liquidez es excepcional
      (spread <= 4.0 bps, depth >= $150k, ker >= 0.45) y bloquea cualquier hora
      si el spread > 8.0 bps o ker < 0.20.
    """
    if spread_bps is not None or ker is not None or depth_usd is not None:
        if spread_bps is not None and float(spread_bps) > 8.0:
            return True
        if ker is not None and float(ker) < 0.20:
            return True
        if (
            spread_bps is not None
            and depth_usd is not None
            and ker is not None
            and float(spread_bps) <= 4.0
            and float(depth_usd) >= 150000.0
            and float(ker) >= 0.45
        ):
            return False
    return int(hour_utc) in TOXIC_UTC_HOURS_SOP137


def calculate_priority_score(symbol: str, confluence_score: float = 70.0) -> float:
    """
    [SOP-97 & SOP-137 ALPHA-TIER PRIORITY SCORING]
    Calcula la puntuación ponderada compartida entre NexusNode y UnifiedBacktestEngine.
    """
    asset = str(symbol or "").upper()
    if any(t1 in asset for t1 in PRIORITY_BOOST_TIER_1_25X):
        multiplier = PRIORITY_TIER_1_MULTIPLIER
    elif any(t2 in asset for t2 in PRIORITY_BOOST_TIER_1_00X):
        multiplier = PRIORITY_TIER_2_MULTIPLIER
    else:
        multiplier = PRIORITY_TIER_3_MULTIPLIER
    return round(float(confluence_score) * multiplier, 2)
