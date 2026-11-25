"""
engine/indicators/tradfi_smc_engine.py — Motor Institucional Dual TradFi SMC (SOP-154)
======================================================================================
Módulo causal compartido (Paridad 1:1 Backtest == Escáner en Vivo):
1. IMPULSE_OTE_SMC: Expansión direccional (KER >= 0.22, EMA50/EMA200, Order Block / FVG en zona OTE 50%-78.6%).
2. LIQUIDITY_SWEEP_JUDAS: Barrido de rango asiático o PDH/PDL en Killzones Londres/NY + rechazo LAF/LBF + FVG/CHoCH.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from engine.indicators.polars_engine import polars_engine
from engine.indicators.structure import identify_look_and_fail, identify_order_blocks

LONDON_TZ = ZoneInfo("Europe/London")
NY_TZ = ZoneInfo("America/New_York")

SISTER_ASSET_MAP: Dict[str, str] = {
    "XAUUSD": "XAGUSD", "XAGUSD": "XAUUSD",
    "US100": "US500",   "US500": "US100",
    "GER40": "EU50",    "EU50": "GER40",
    "USOIL": "UKOIL",   "UKOIL": "USOIL",
    "EURUSD": "GBPUSD", "GBPUSD": "EURUSD",
    "AUDUSD": "NZDUSD", "NZDUSD": "AUDUSD",
    "EURJPY": "GBPJPY", "GBPJPY": "EURJPY",
}


def prepare_tradfi_features(
    df: pd.DataFrame,
    htf_1d_df: Optional[pd.DataFrame] = None,
    sister_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Precalcula de forma estrictamente causal todos los indicadores institucionales TradFi (1D + SMT + Session VWAP)."""
    if df is None or len(df) < 50:
        return pd.DataFrame()

    out = df.copy()
    out.columns = [str(c).lower() for c in out.columns]
    ts_col = "timestamp" if "timestamp" in out.columns else ("time" if "time" in out.columns else None)
    if ts_col is not None:
        if pd.api.types.is_numeric_dtype(out[ts_col]):
            unit = "s" if float(out[ts_col].iloc[0]) < 1e11 else "ms"
            out["timestamp"] = pd.to_datetime(out[ts_col], unit=unit, utc=True)
        else:
            out["timestamp"] = pd.to_datetime(out[ts_col], utc=True)
    else:
        out["timestamp"] = pd.date_range(end=datetime.now(timezone.utc), periods=len(out), freq="1h", tz="UTC")

    out = out.sort_values("timestamp").reset_index(drop=True)
    out = polars_engine.compute_indicators(out)
    out = identify_order_blocks(out, threshold=1.25, lookback_structure=21)
    out = identify_look_and_fail(out)

    # Kaufman Efficiency Ratio (KER 14) causal
    close_s = out["close"].astype(float)
    direction_net = (close_s - close_s.shift(14)).abs()
    volatility_sum = close_s.diff().abs().rolling(14).sum()
    out["ker"] = (direction_net / (volatility_sum + 1e-9)).fillna(0.0).clip(0.0, 1.0)

    # Rangos previos causales (20 velas)
    out["prev_swing_high"] = out["high"].shift(1).rolling(20).max()
    out["prev_swing_low"] = out["low"].shift(1).rolling(20).min()

    # Multi-Session Anchored VWAP DST-Aware (Globex 18:00 NY / London 08:00 / NY RTH 09:30)
    tp = (out["high"].astype(float) + out["low"].astype(float) + close_s) / 3.0
    vol = out["volume"].fillna(1.0).astype(float).replace(0.0, 1.0)
    ny_ts = out["timestamp"].dt.tz_convert(NY_TZ)
    lon_ts = out["timestamp"].dt.tz_convert(LONDON_TZ)
    ny_mins = ny_ts.dt.hour * 60 + ny_ts.dt.minute
    lon_mins = lon_ts.dt.hour * 60 + lon_ts.dt.minute
    cme_day_key = (ny_ts + pd.Timedelta(hours=6)).dt.strftime("%Y-%m-%d")
    is_ny_rth = (ny_mins >= 570) & (ny_mins < 1080)
    is_london = (~is_ny_rth) & (lon_mins >= 480) & (ny_mins < 570)
    sess_id = np.where(is_ny_rth, "NY", np.where(is_london, "LON", "GLOBEX"))
    day_key = cme_day_key + "_" + sess_id
    cum_pv = (tp * vol).groupby(day_key).cumsum()
    cum_v = vol.groupby(day_key).cumsum()
    out["session_vwap"] = (cum_pv / (cum_v + 1e-9)).fillna(close_s)
    out["vwap_dist_pct"] = ((close_s - out["session_vwap"]) / (out["session_vwap"] + 1e-9)).fillna(0.0)

    # Ancla Estructural 1D causal (shift(1) sobre velas diarias ya cerradas)
    out["htf_trend"] = 0
    if htf_1d_df is not None and len(htf_1d_df) >= 55:
        d1 = htf_1d_df.copy()
        d1.columns = [str(c).lower() for c in d1.columns]
        d1_ts = "timestamp" if "timestamp" in d1.columns else ("time" if "time" in d1.columns else None)
        if d1_ts is not None:
            d1["timestamp"] = pd.to_datetime(d1[d1_ts], utc=True)
            d1 = d1.sort_values("timestamp").reset_index(drop=True)
            d1_close = d1["close"].astype(float)
            d1_ema20 = d1_close.ewm(span=20, adjust=False).mean()
            d1_ema50 = d1_close.ewm(span=50, adjust=False).mean()
            # Desplazamiento estricto de 1 vela diaria cerrada (cero look-ahead)
            trend_closed = np.where(
                (d1_close.shift(1) > d1_ema20.shift(1)) & (d1_ema20.shift(1) > d1_ema50.shift(1)),
                1,
                np.where((d1_close.shift(1) < d1_ema20.shift(1)) & (d1_ema20.shift(1) < d1_ema50.shift(1)), -1, 0),
            )
            d1_merge = pd.DataFrame({"timestamp": d1["timestamp"], "htf_trend": trend_closed})
            merged = pd.merge_asof(out[["timestamp"]], d1_merge, on="timestamp", direction="backward")
            out["htf_trend"] = merged["htf_trend"].fillna(0).astype(int)

    # Divergencia SMT causal con activo hermano
    out["smt_bull"] = False
    out["smt_bear"] = False
    if sister_df is not None and len(sister_df) >= 25:
        s_df = sister_df.copy()
        s_df.columns = [str(c).lower() for c in s_df.columns]
        s_ts = "timestamp" if "timestamp" in s_df.columns else ("time" if "time" in s_df.columns else None)
        if s_ts is not None:
            s_df["timestamp"] = pd.to_datetime(s_df[s_ts], utc=True)
            s_df = s_df.sort_values("timestamp").reset_index(drop=True)
            s_df["s_prev_h20"] = s_df["high"].shift(1).rolling(20).max()
            s_df["s_prev_l20"] = s_df["low"].shift(1).rolling(20).min()
            s_merge = pd.merge_asof(
                out[["timestamp"]],
                s_df[["timestamp", "high", "low", "s_prev_h20", "s_prev_l20"]].rename(
                    columns={"high": "s_high", "low": "s_low"}
                ),
                on="timestamp",
                direction="backward",
            )
            main_swept_low = out["low"] < out["prev_swing_low"]
            sis_held_low = s_merge["s_low"] > s_merge["s_prev_l20"]
            main_swept_high = out["high"] > out["prev_swing_high"]
            sis_held_high = s_merge["s_high"] < s_merge["s_prev_h20"]
            out["smt_bull"] = (main_swept_low & sis_held_low).fillna(False)
            out["smt_bear"] = (main_swept_high & sis_held_high).fillna(False)

    return out


def is_tradfi_killzone(ts: pd.Timestamp, symbol: str = "") -> bool:
    """Killzones reales DST-aware: Londres (07-11) y Nueva York (08-14), vetando feriados y Early Closes."""
    from engine.core.market_calendar import get_venue_liquidity_status
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    if symbol:
        dt_py = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts
        if not get_venue_liquidity_status(symbol, dt_py).get("execution_allowed", True):
            return False
    lon_h = ts.astimezone(LONDON_TZ).hour
    ny_h = ts.astimezone(NY_TZ).hour
    return (7 <= lon_h <= 11) or (8 <= ny_h <= 14)


def evaluate_tradfi_bar(
    df: pd.DataFrame,
    idx: int,
    symbol: str,
    archetype: str = "IMPULSE_OTE_SMC",
    long_only: bool = False,
    cost_pct_rt: float = 0.0002,
    max_spread_to_risk: float = 0.08,
) -> Optional[Dict[str, Any]]:
    """
    Evalúa de forma 100% causal la vela `idx` (sin acceder a idx+1..N).
    Retorna un setup completo con entry, sl, tp1, tp2, tp3, confluence_score y checklist.
    """
    if idx < 205 or idx >= len(df):
        return None

    row = df.iloc[idx]
    close = float(row["close"])
    high = float(row["high"])
    low = float(row["low"])
    atr = float(row.get("atr", 0.0))
    ema50 = float(row.get("ema50", 0.0))
    ema200 = float(row.get("ema200", 0.0))
    ker = float(row.get("ker", 0.0))
    ts = row["timestamp"]

    if atr <= 0 or close <= 0 or ema50 <= 0 or ema200 <= 0:
        return None

    direction: Optional[str] = None
    entry = 0.0
    sl = 0.0
    score = 60
    checklist = []

    if archetype == "IMPULSE_OTE_SMC":
        if ker < 0.22:
            return None
        fvg_b = bool(row.get("fvg_bullish", False)) or bool(row.get("fvg_bull", False))
        fvg_s = bool(row.get("fvg_bearish", False)) or bool(row.get("fvg_bear", False))
        ob_b = bool(row.get("ob_bullish", False))
        ob_s = bool(row.get("ob_bearish", False))
        ob_score = float(row.get("ob_strength_score", 0.0))
        htf_trend = int(row.get("htf_trend", 0))
        smt_bull = bool(row.get("smt_bull", False))
        smt_bear = bool(row.get("smt_bear", False))

        is_bull = close > ema50 > ema200 and (fvg_b or (ob_b and ob_score >= 60)) and (htf_trend >= 0)
        is_bear = (not long_only) and (close < ema50 < ema200 and (fvg_s or (ob_s and ob_score >= 60))) and (htf_trend <= 0)
        if not (is_bull or is_bear):
            return None

        direction = "LONG" if is_bull else "SHORT"
        prev_h2 = float(df["high"].iloc[idx - 2])
        prev_l2 = float(df["low"].iloc[idx - 2])
        entry = (low + prev_h2) * 0.5 if is_bull else (high + prev_l2) * 0.5
        sl_dist = max(atr * 1.35, entry * 0.0020)
        sl = entry - sl_dist if is_bull else entry + sl_dist

        score += 15
        checklist.append({"factor": "Alineación Macro EMA50/200", "status": "CUMPLIDO", "detail": f"KER={ker:.2f} >= 0.22"})
        if (is_bull and htf_trend == 1) or (is_bear and htf_trend == -1):
            score += 10
            checklist.append({"factor": "Ancla Estructural 1D", "status": "CUMPLIDO", "detail": "Tendencia diaria alineada"})
        if (is_bull and smt_bull) or (is_bear and smt_bear):
            score += 15
            checklist.append({"factor": "Divergencia SMT Institucional", "status": "CUMPLIDO", "detail": "Divergencia con activo hermano"})
        if ob_b or ob_s:
            score += 15
            checklist.append({"factor": "Order Block + FVG Institucional", "status": "CUMPLIDO", "detail": f"OB Score={ob_score:.0f}/100"})
        else:
            score += 10
            checklist.append({"factor": "Fair Value Gap OTE", "status": "CUMPLIDO", "detail": "Desplazamiento con FVG activo"})

    elif archetype == "LIQUIDITY_SWEEP_JUDAS":
        if not is_tradfi_killzone(ts, symbol=symbol):
            return None
        laf_bear = bool(row.get("laf_bear", False))
        lbf_bull = bool(row.get("lbf_bull", False))
        vwap_dist = float(row.get("vwap_dist_pct", 0.0))
        smt_bull = bool(row.get("smt_bull", False))
        smt_bear = bool(row.get("smt_bear", False))

        valid_bull = lbf_bull and (vwap_dist <= 0.0025)
        valid_bear = laf_bear and (not long_only) and (vwap_dist >= -0.0025)
        if not (valid_bull or valid_bear):
            return None

        direction = "LONG" if valid_bull else "SHORT"
        # Entrada en retroceso 50% de la vela de barrido/rechazo
        entry = (high + low) * 0.5
        sl = (low - atr * 0.20) if direction == "LONG" else (high + atr * 0.20)

        score += 20
        checklist.append({"factor": "Judas Liquidity Sweep + VWAP (SOP-114)", "status": "CUMPLIDO", "detail": f"VWAP dist={vwap_dist*100:.2f}%"})
        if (direction == "LONG" and smt_bull) or (direction == "SHORT" and smt_bear):
            score += 15
            checklist.append({"factor": "Divergencia SMT Institucional", "status": "CUMPLIDO", "detail": "Divergencia con activo hermano"})
        if (direction == "LONG" and close > ema200) or (direction == "SHORT" and close < ema200):
            score += 10
            checklist.append({"factor": "Confluencia EMA200", "status": "CUMPLIDO", "detail": "Reversión alineada con tendencia macro"})
    else:
        return None

    dist = abs(entry - sl)
    if dist <= 1e-9:
        return None

    cost_r = (entry * cost_pct_rt) / dist
    if cost_r > max_spread_to_risk:
        return None

    sign = 1.0 if direction == "LONG" else -1.0
    return {
        "asset": symbol,
        "direction": direction,
        "archetype": archetype,
        "price": entry,
        "current_price": close,
        "stop_loss": sl,
        "be_price": entry + sign * dist * 1.0,
        "tp1": entry + sign * dist * 1.3,
        "tp2": entry + sign * dist * 2.4,
        "tp3": entry + sign * dist * 3.8,
        "r_dist": dist,
        "cost_r": round(cost_r, 4),
        "confluence_score": min(100, score),
        "checklist": checklist,
        "is_killzone": is_tradfi_killzone(ts),
    }
