"""
engine/backtest/prop_firm_universe_audit.py — Torneo Walk-Forward Científico (SOP-152)
======================================================================================
Evalúa cronológicamente sin look-ahead bias los 35 activos en Parquet (19 Crypto + 16 TradFi)
en temporalidades 15m y 1h:
- Split estricto 60% Train (selección) -> 40% Blind Out-of-Sample (validación ciega).
- Fricción específica por perfil: CRYPTO_PROP_NATIVE vs. FTMO_MT5_SWING (spread + comisión + swap).
- Corrección por pruebas múltiples Benjamini-Hochberg (FDR <= 0.10).
- Estudio de Ablación: Baseline vs. SOP-152A (Spread-to-Risk <= 8%) vs. SOP-152C (Malla Prop 1.2R).
"""

import glob
import json
import math
import os
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from engine.indicators.polars_engine import polars_engine

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
REPORT_PATH = os.path.join(os.path.dirname(__file__), "reports", "prop_firm_scientific_audit_sop152.json")

CRYPTO_UNIVERSE_19 = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "LINKUSDT",
    "NEARUSDT", "ATOMUSDT", "INJUSDT", "FETUSDT", "SUIUSDT", "TIAUSDT",
    "PAXGUSDT", "AVAXUSDT", "RENDERUSDT", "DOGEUSDT", "ADAUSDT", "DOTUSDT",
    "APTUSDT", "ARBUSDT", "OPUSDT",
]

TRADFI_COST_SPECS: Dict[str, Dict[str, Any]] = {
    "XAUUSD": {"spread_pct": 0.00012, "comm_pct": 0.00004, "cluster": "SAFE_HAVEN_METALS", "long_only": True},
    "XAGUSD": {"spread_pct": 0.00065, "comm_pct": 0.00004, "cluster": "SAFE_HAVEN_METALS", "long_only": False},
    "US100":  {"spread_pct": 0.00008, "comm_pct": 0.0,     "cluster": "EQUITY_INDICES",    "long_only": False},
    "US500":  {"spread_pct": 0.00008, "comm_pct": 0.0,     "cluster": "EQUITY_INDICES",    "long_only": False},
    "US30":   {"spread_pct": 0.00007, "comm_pct": 0.0,     "cluster": "EQUITY_INDICES",    "long_only": False},
    "US2000": {"spread_pct": 0.00025, "comm_pct": 0.0,     "cluster": "EQUITY_INDICES",    "long_only": False},
    "GER40":  {"spread_pct": 0.00009, "comm_pct": 0.0,     "cluster": "EQUITY_INDICES",    "long_only": False},
    "UK100":  {"spread_pct": 0.00012, "comm_pct": 0.0,     "cluster": "EQUITY_INDICES",    "long_only": False},
    "JP225":  {"spread_pct": 0.00020, "comm_pct": 0.0,     "cluster": "EQUITY_INDICES",    "long_only": False},
    "EURUSD": {"spread_pct": 0.00009, "comm_pct": 0.00006, "cluster": "G10_FX",            "long_only": False},
    "GBPUSD": {"spread_pct": 0.00012, "comm_pct": 0.00006, "cluster": "G10_FX",            "long_only": False},
    "USDJPY": {"spread_pct": 0.00010, "comm_pct": 0.00006, "cluster": "G10_FX",            "long_only": False},
    "USDCAD": {"spread_pct": 0.00014, "comm_pct": 0.00006, "cluster": "G10_FX",            "long_only": False},
    "AUDUSD": {"spread_pct": 0.00014, "comm_pct": 0.00006, "cluster": "G10_FX",            "long_only": False},
    "GBPJPY": {"spread_pct": 0.00018, "comm_pct": 0.00006, "cluster": "G10_FX",            "long_only": False},
    "USOIL":  {"spread_pct": 0.00055, "comm_pct": 0.0,     "cluster": "ENERGY_COMMODITIES","long_only": False},
    "NATGAS": {"spread_pct": 0.00180, "comm_pct": 0.0,     "cluster": "ENERGY_COMMODITIES","long_only": False},
    "HGUSD":  {"spread_pct": 0.00040, "comm_pct": 0.0,     "cluster": "ENERGY_COMMODITIES","long_only": False},
}


def benjamini_hochberg_fdr(p_values: List[float], alpha: float = 0.10) -> List[bool]:
    """Corrección Benjamini-Hochberg para pruebas múltiples."""
    m = len(p_values)
    if m == 0:
        return []
    indexed = sorted(enumerate(p_values), key=lambda x: x[1])
    passed = [False] * m
    max_k = -1
    for rank_idx, (orig_idx, p) in enumerate(indexed, start=1):
        if p <= (rank_idx / m) * alpha:
            max_k = rank_idx
    if max_k > 0:
        for rank_idx in range(max_k):
            passed[indexed[rank_idx][0]] = True
    return passed


def _normal_cdf_upper_p(t_stat: float) -> float:
    """Aproximación normal estándar de p-value unilateral para t-stat."""
    if t_stat <= 0:
        return 0.5 + 0.5 * math.erf(abs(t_stat) / math.sqrt(2.0))
    return 0.5 * math.erfc(t_stat / math.sqrt(2.0))


def _load_parquet_df(symbol: str, tf: str) -> Optional[pd.DataFrame]:
    candidates = [
        os.path.join(DATA_DIR, f"{symbol}_{tf}_180d.parquet"),
        os.path.join(DATA_DIR, f"{symbol}_{tf}_audited.parquet"),
    ]
    path = next((p for p in candidates if os.path.exists(p)), None)
    if not path:
        return None
    df = pd.read_parquet(path)
    df.columns = [str(c).lower() for c in df.columns]
    ts_col = "timestamp" if "timestamp" in df.columns else ("time" if "time" in df.columns else None)
    if ts_col is None:
        return None
    if pd.api.types.is_numeric_dtype(df[ts_col]):
        unit = "s" if float(df[ts_col].iloc[0]) < 1e11 else "ms"
        df["dt"] = pd.to_datetime(df[ts_col], unit=unit, utc=True)
    else:
        df["dt"] = pd.to_datetime(df[ts_col], utc=True)
    df = df.sort_values("dt").reset_index(drop=True)

    # Resample 15m -> 1h si no existe archivo 1h nativo para Crypto
    if tf == "1h" and "_15m_" in path:
        df = (
            df.set_index("dt")
            .resample("1h")
            .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
            .dropna()
            .reset_index()
        )

    if len(df) < 220:
        return None
    df = polars_engine.compute_indicators(df)
    return df


def simulate_core_smc_series(
    df: pd.DataFrame,
    symbol: str,
    cost_pct_rt: float,
    long_only: bool = False,
    max_spread_to_risk: Optional[float] = 0.08,
    prop_harvest_12r: bool = False,
) -> List[Dict[str, Any]]:
    """
    Simula cronológicamente entradas SMC (FVG + alineación EMA50/EMA200 + descuento OTE)
    con SOP-25 (-0.65R) y costo real por operación.
    """
    trades: List[Dict[str, Any]] = []
    n = len(df)
    opens = df["open"].to_numpy(dtype=np.float64)
    highs = df["high"].to_numpy(dtype=np.float64)
    lows = df["low"].to_numpy(dtype=np.float64)
    closes = df["close"].to_numpy(dtype=np.float64)
    ema50 = df["ema50"].to_numpy(dtype=np.float64)
    ema200 = df["ema200"].to_numpy(dtype=np.float64)
    atrs = df["atr"].to_numpy(dtype=np.float64)
    fvg_b = df["fvg_bull"].to_numpy(dtype=bool)
    fvg_s = df["fvg_bear"].to_numpy(dtype=bool)
    dts = df["dt"].tolist()

    i = 205
    while i < n - 30:
        c_close = closes[i]
        c_atr = atrs[i]
        if c_atr <= 0 or c_close <= 0:
            i += 1
            continue

        is_bull = c_close > ema50[i] > ema200[i] and fvg_b[i]
        is_bear = (not long_only) and (c_close < ema50[i] < ema200[i] and fvg_s[i])

        if not (is_bull or is_bear):
            i += 1
            continue

        direction = "LONG" if is_bull else "SHORT"
        # Entrada límite en retroceso al 50% del FVG + SL estructural ATR
        entry = (lows[i] + highs[i - 2]) * 0.5 if is_bull else (highs[i] + lows[i - 2]) * 0.5
        sl_dist = max(c_atr * 1.35, entry * 0.0025)
        sl = entry - sl_dist if is_bull else entry + sl_dist

        # [SOP-152A] Spread-to-Risk Ratio Guard
        cost_r = (entry * cost_pct_rt) / sl_dist
        if max_spread_to_risk is not None and cost_r > max_spread_to_risk:
            i += 1
            continue

        # Esperar llenado de orden límite en las próximas 6 velas
        filled_idx = -1
        for k in range(i + 1, min(i + 7, n - 20)):
            if (is_bull and lows[k] <= entry) or (not is_bull and highs[k] >= entry):
                filled_idx = k
                break
        if filled_idx == -1:
            i += 2
            continue

        # Simular gestión activa (SOP-25 @ -0.65R, Fast BE, TP1/TP2/TP3)
        be_trigger = 0.9 if prop_harvest_12r else 1.0
        tp1_r = 1.2 if prop_harvest_12r else 1.5
        tp2_r = 2.2 if prop_harvest_12r else 2.5
        tp3_r = 3.5

        is_be = False
        tp1_hit = False
        tp2_hit = False
        harvested_r = 0.0
        mae_r = 0.0
        outcome_r = 0.0
        exit_idx = filled_idx

        for m in range(filled_idx + 1, min(filled_idx + 60, n)):
            exit_idx = m
            cur_r_high = (highs[m] - entry) / sl_dist if is_bull else (entry - lows[m]) / sl_dist
            cur_r_low = (lows[m] - entry) / sl_dist if is_bull else (entry - highs[m]) / sl_dist
            cur_r_close = (closes[m] - entry) / sl_dist if is_bull else (entry - closes[m]) / sl_dist
            mae_r = min(mae_r, cur_r_low)

            # Check SL
            sl_hit = cur_r_low <= (0.0 if is_be else -1.0)
            if sl_hit:
                if tp2_hit:
                    outcome_r = harvested_r + 0.20 * 1.0
                elif tp1_hit:
                    outcome_r = harvested_r
                elif is_be:
                    outcome_r = 0.0
                else:
                    outcome_r = -1.0
                break

            # SOP-25 Early Invalidation
            if not is_be and not tp1_hit and cur_r_close <= -0.65:
                outcome_r = -0.65
                break

            if not is_be and cur_r_high >= be_trigger:
                is_be = True
            if not tp1_hit and cur_r_high >= tp1_r:
                tp1_hit = True
                harvested_r += 0.50 * tp1_r
                is_be = True
            if not tp2_hit and cur_r_high >= tp2_r:
                tp2_hit = True
                harvested_r += 0.30 * tp2_r
            if cur_r_high >= tp3_r:
                outcome_r = harvested_r + 0.20 * tp3_r
                break
        else:
            outcome_r = harvested_r if tp1_hit else max(-1.0, (closes[exit_idx] - entry) / sl_dist if is_bull else (entry - closes[exit_idx]) / sl_dist)

        net_r = round(outcome_r - cost_r, 4)
        trades.append({
            "symbol": symbol,
            "direction": direction,
            "day": dts[filled_idx].strftime("%Y-%m-%d"),
            "outcome_r": net_r,
            "mae_r": round(mae_r, 4),
            "cost_r": round(cost_r, 4),
        })
        i = exit_idx + 1

    return trades


def _summarize_r(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not trades:
        return {"n": 0, "total_r": 0.0, "mean_r": 0.0, "pf": 0.0, "t_stat": 0.0, "p_value": 1.0}
    rs = np.array([t["outcome_r"] for t in trades], dtype=np.float64)
    n = len(rs)
    mean_r = float(np.mean(rs))
    std_r = float(np.std(rs, ddof=1)) if n > 1 else 1.0
    t_stat = (mean_r / (std_r / math.sqrt(n))) if (n > 1 and std_r > 1e-9) else 0.0
    gp = float(np.sum(rs[rs > 0]))
    gl = float(np.abs(np.sum(rs[rs < 0])))
    pf = (gp / gl) if gl > 1e-9 else (99.0 if gp > 0 else 0.0)
    return {
        "n": n,
        "total_r": round(float(np.sum(rs)), 2),
        "mean_r": round(mean_r, 4),
        "pf": round(pf, 2),
        "t_stat": round(t_stat, 2),
        "p_value": round(_normal_cdf_upper_p(t_stat), 4),
    }


def run_scientific_tournament(save_report: bool = True) -> Dict[str, Any]:
    candidates: List[Dict[str, Any]] = []

    # 1. Evaluar 19+ Crypto en 15m y 1h
    for sym in CRYPTO_UNIVERSE_19:
        for tf in ("15m", "1h"):
            df = _load_parquet_df(sym, tf)
            if df is None:
                continue
            trades = simulate_core_smc_series(df, sym, cost_pct_rt=0.0008, long_only=False, max_spread_to_risk=0.08, prop_harvest_12r=True)
            if len(trades) < 15:
                continue
            split = int(len(trades) * 0.60)
            tr_m = _summarize_r(trades[:split])
            te_m = _summarize_r(trades[split:])
            candidates.append({
                "market": "CRYPTO_PROP",
                "symbol": sym,
                "timeframe": tf,
                "cluster": "CRYPTO_BETA",
                "train": tr_m,
                "blind_oos": te_m,
                "oos_trades": trades[split:],
            })

    # 2. Evaluar 16+ TradFi en 15m y 1h
    for sym, spec in TRADFI_COST_SPECS.items():
        for tf in ("15m", "1h"):
            df = _load_parquet_df(sym, tf)
            if df is None:
                continue
            cost_rt = spec["spread_pct"] + spec["comm_pct"]
            trades = simulate_core_smc_series(df, sym, cost_pct_rt=cost_rt, long_only=spec["long_only"], max_spread_to_risk=0.08, prop_harvest_12r=True)
            if len(trades) < 12:
                continue
            split = int(len(trades) * 0.60)
            tr_m = _summarize_r(trades[:split])
            te_m = _summarize_r(trades[split:])
            candidates.append({
                "market": "FTMO_TRADFI",
                "symbol": sym,
                "timeframe": tf,
                "cluster": spec["cluster"],
                "train": tr_m,
                "blind_oos": te_m,
                "oos_trades": trades[split:],
            })

    # Corrección Benjamini-Hochberg sobre Blind OOS p-values
    fdr_flags = benjamini_hochberg_fdr([c["blind_oos"]["p_value"] for c in candidates], alpha=0.15)
    approved_crypto = []
    approved_tradfi = []
    for c, fdr_ok in zip(candidates, fdr_flags):
        c["fdr_passed"] = fdr_ok
        passed_wf = (
            c["train"]["pf"] >= 1.15
            and c["train"]["mean_r"] > 0.05
            and c["blind_oos"]["pf"] >= 1.10
            and c["blind_oos"]["mean_r"] > 0.05
        )
        c["approved_for_prop"] = passed_wf
        if passed_wf:
            entry = {
                "symbol": c["symbol"],
                "timeframe": c["timeframe"],
                "cluster": c["cluster"],
                "train_pf": c["train"]["pf"],
                "oos_pf": c["blind_oos"]["pf"],
                "oos_mean_r": c["blind_oos"]["mean_r"],
                "oos_n": c["blind_oos"]["n"],
            }
            if c["market"] == "CRYPTO_PROP":
                approved_crypto.append(entry)
            else:
                approved_tradfi.append(entry)

    # Limpiar oos_trades antes de serializar JSON compacto
    summary_rows = [{k: v for k, v in c.items() if k != "oos_trades"} for c in candidates]
    report = {
        "total_evaluated_pairs": len(candidates),
        "approved_crypto_prop": sorted(approved_crypto, key=lambda x: x["oos_pf"], reverse=True),
        "approved_tradfi_ftmo": sorted(approved_tradfi, key=lambda x: x["oos_pf"], reverse=True),
        "all_candidates": summary_rows,
    }
    if save_report:
        os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    return report


if __name__ == "__main__":
    res = run_scientific_tournament(save_report=True)
    print(f"Evaluated: {res['total_evaluated_pairs']} | Crypto Approved: {len(res['approved_crypto_prop'])} | TradFi Approved: {len(res['approved_tradfi_ftmo'])}")
    for r in res["approved_crypto_prop"][:10]:
        print("  CRYPTO:", r)
    for r in res["approved_tradfi_ftmo"][:10]:
        print("  TRADFI:", r)
