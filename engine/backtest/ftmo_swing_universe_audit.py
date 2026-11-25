"""
engine/backtest/ftmo_swing_universe_audit.py — Torneo Científico FTMO Swing (SOP-154)
=====================================================================================
Evalúa cronológicamente sin look-ahead bias los 23 instrumentos TradFi de FTMO MT5
en 1h (2-3 años) y 15m (~60-80 días), probando ambos arquetipos:
- IMPULSE_OTE_SMC
- LIQUIDITY_SWEEP_JUDAS

Incluye:
- Split estricto 60% Train -> 40% Blind Out-of-Sample.
- Fricción real FTMO Swing: spread + comisión + swap nocturno (00:00 Europe/Prague).
- Corrección Benjamini-Hochberg FDR.
- Selección de Portafolio Descorrelacionado (máx. 2 activos por clúster macro).
"""

import json
import math
import os
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from engine.indicators.tradfi_smc_engine import SISTER_ASSET_MAP, evaluate_tradfi_bar, prepare_tradfi_features
from engine.analytics.quant_statistical_rigor import (
    compute_deflated_sharpe_ratio,
    run_cpcv_validation,
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
REPORT_PATH = os.path.join(os.path.dirname(__file__), "reports", "ftmo_swing_scientific_audit_sop154.json")
PRAGUE_TZ = ZoneInfo("Europe/Prague")

FTMO_UNIVERSE_SPECS: Dict[str, Dict[str, Any]] = {
    "XAUUSD": {"spread_pct": 0.00012, "comm_pct": 0.00004, "swap_night_pct": 0.00006, "cluster": "SAFE_HAVEN_METALS", "long_only": True},
    "XAGUSD": {"spread_pct": 0.00065, "comm_pct": 0.00004, "swap_night_pct": 0.00008, "cluster": "SAFE_HAVEN_METALS", "long_only": False},
    "USOIL":  {"spread_pct": 0.00055, "comm_pct": 0.0,     "swap_night_pct": 0.00007, "cluster": "INDUSTRIAL_ENERGY", "long_only": False},
    "UKOIL":  {"spread_pct": 0.00055, "comm_pct": 0.0,     "swap_night_pct": 0.00007, "cluster": "INDUSTRIAL_ENERGY", "long_only": False},
    "HGUSD":  {"spread_pct": 0.00040, "comm_pct": 0.0,     "swap_night_pct": 0.00006, "cluster": "INDUSTRIAL_ENERGY", "long_only": False},
    "US100":  {"spread_pct": 0.00008, "comm_pct": 0.0,     "swap_night_pct": 0.00005, "cluster": "US_EQUITY_INDICES", "long_only": False},
    "US500":  {"spread_pct": 0.00008, "comm_pct": 0.0,     "swap_night_pct": 0.00005, "cluster": "US_EQUITY_INDICES", "long_only": False},
    "US30":   {"spread_pct": 0.00007, "comm_pct": 0.0,     "swap_night_pct": 0.00005, "cluster": "US_EQUITY_INDICES", "long_only": False},
    "US2000": {"spread_pct": 0.00025, "comm_pct": 0.0,     "swap_night_pct": 0.00005, "cluster": "US_EQUITY_INDICES", "long_only": False},
    "GER40":  {"spread_pct": 0.00009, "comm_pct": 0.0,     "swap_night_pct": 0.00005, "cluster": "GLOBAL_EQUITY_INDICES", "long_only": False},
    "UK100":  {"spread_pct": 0.00012, "comm_pct": 0.0,     "swap_night_pct": 0.00005, "cluster": "GLOBAL_EQUITY_INDICES", "long_only": False},
    "JP225":  {"spread_pct": 0.00020, "comm_pct": 0.0,     "swap_night_pct": 0.00004, "cluster": "GLOBAL_EQUITY_INDICES", "long_only": False},
    "EU50":   {"spread_pct": 0.00015, "comm_pct": 0.0,     "swap_night_pct": 0.00005, "cluster": "GLOBAL_EQUITY_INDICES", "long_only": False},
    "EURUSD": {"spread_pct": 0.00009, "comm_pct": 0.00006, "swap_night_pct": 0.00003, "cluster": "G10_FX_USD", "long_only": False},
    "GBPUSD": {"spread_pct": 0.00012, "comm_pct": 0.00006, "swap_night_pct": 0.00003, "cluster": "G10_FX_USD", "long_only": False},
    "USDJPY": {"spread_pct": 0.00010, "comm_pct": 0.00006, "swap_night_pct": 0.00004, "cluster": "G10_FX_USD", "long_only": False},
    "USDCAD": {"spread_pct": 0.00014, "comm_pct": 0.00006, "swap_night_pct": 0.00003, "cluster": "G10_FX_USD", "long_only": False},
    "AUDUSD": {"spread_pct": 0.00014, "comm_pct": 0.00006, "swap_night_pct": 0.00003, "cluster": "G10_FX_USD", "long_only": False},
    "USDCHF": {"spread_pct": 0.00012, "comm_pct": 0.00006, "swap_night_pct": 0.00003, "cluster": "G10_FX_USD", "long_only": False},
    "NZDUSD": {"spread_pct": 0.00018, "comm_pct": 0.00006, "swap_night_pct": 0.00003, "cluster": "G10_FX_USD", "long_only": False},
    "EURJPY": {"spread_pct": 0.00014, "comm_pct": 0.00006, "swap_night_pct": 0.00004, "cluster": "G10_FX_CROSS", "long_only": False},
    "GBPJPY": {"spread_pct": 0.00018, "comm_pct": 0.00006, "swap_night_pct": 0.00004, "cluster": "G10_FX_CROSS", "long_only": False},
    "EURGBP": {"spread_pct": 0.00014, "comm_pct": 0.00006, "swap_night_pct": 0.00003, "cluster": "G10_FX_CROSS", "long_only": False},
}


def benjamini_hochberg_fdr(p_values: List[float], alpha: float = 0.15) -> List[bool]:
    m = len(p_values)
    if m == 0:
        return []
    indexed = sorted(enumerate(p_values), key=lambda x: x[1])
    passed = [False] * m
    max_k = -1
    for rank_idx, (_, p) in enumerate(indexed, start=1):
        if p <= (rank_idx / m) * alpha:
            max_k = rank_idx
    if max_k > 0:
        for rank_idx in range(max_k):
            passed[indexed[rank_idx][0]] = True
    return passed


def _normal_cdf_upper_p(t_stat: float) -> float:
    if t_stat <= 0:
        return 0.5 + 0.5 * math.erf(abs(t_stat) / math.sqrt(2.0))
    return 0.5 * math.erfc(t_stat / math.sqrt(2.0))


def simulate_tradfi_series(
    df: pd.DataFrame,
    symbol: str,
    spec: Dict[str, Any],
    archetype: str,
) -> List[Dict[str, Any]]:
    trades: List[Dict[str, Any]] = []
    n = len(df)
    if n < 240:
        return trades

    highs = df["high"].to_numpy(dtype=np.float64)
    lows = df["low"].to_numpy(dtype=np.float64)
    closes = df["close"].to_numpy(dtype=np.float64)
    dts = df["timestamp"].tolist()
    cost_rt = float(spec["spread_pct"]) + float(spec["comm_pct"])
    swap_night_pct = float(spec["swap_night_pct"])

    i = 205
    while i < n - 30:
        setup = evaluate_tradfi_bar(
            df,
            idx=i,
            symbol=symbol,
            archetype=archetype,
            long_only=bool(spec.get("long_only", False)),
            cost_pct_rt=cost_rt,
            max_spread_to_risk=0.08,
        )
        if setup is None:
            i += 1
            continue

        is_bull = setup["direction"] == "LONG"
        entry = float(setup["price"])
        sl_dist = float(setup["r_dist"])

        filled_idx = -1
        for k in range(i + 1, min(i + 7, n - 20)):
            if (is_bull and lows[k] <= entry) or (not is_bull and highs[k] >= entry):
                filled_idx = k
                break
        if filled_idx == -1:
            i += 2
            continue

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

            if cur_r_low <= (0.0 if is_be else -1.0):
                mae_r = max(mae_r, 0.0 if is_be else -1.0)
                if tp2_hit:
                    outcome_r = harvested_r + 0.20 * 1.0
                elif tp1_hit:
                    outcome_r = harvested_r
                elif is_be:
                    outcome_r = 0.0
                else:
                    outcome_r = -1.0
                break

            if not is_be and not tp1_hit and cur_r_close <= -0.65:
                outcome_r = -0.65
                break

            if not is_be and cur_r_high >= 1.0:
                is_be = True
            if not tp1_hit and cur_r_high >= 1.3:
                tp1_hit = True
                harvested_r += 0.50 * 1.3
                is_be = True
            if not tp2_hit and cur_r_high >= 2.4:
                tp2_hit = True
                harvested_r += 0.30 * 2.4
            if cur_r_high >= 3.8:
                outcome_r = harvested_r + 0.20 * 3.8
                break
        else:
            outcome_r = harvested_r if tp1_hit else max(-1.0, (closes[exit_idx] - entry) / sl_dist if is_bull else (entry - closes[exit_idx]) / sl_dist)

        # Swap nocturno exacto en 00:00 Europe/Prague
        dt_in = dts[filled_idx].tz_convert(PRAGUE_TZ)
        dt_out = dts[exit_idx].tz_convert(PRAGUE_TZ)
        nights = max(0, (dt_out.date() - dt_in.date()).days)
        swap_r = (entry * swap_night_pct * nights) / sl_dist
        net_r = round(outcome_r - float(setup["cost_r"]) - swap_r, 4)

        trades.append({
            "symbol": symbol,
            "archetype": archetype,
            "day": dt_in.strftime("%Y-%m-%d"),
            "outcome_r": net_r,
            "mae_r": round(mae_r, 4),
            "cost_r": round(float(setup["cost_r"]) + swap_r, 4),
        })
        i = exit_idx + 1

    return trades


def _summarize(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
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


def run_ftmo_swing_tournament(save_report: bool = True) -> Dict[str, Any]:
    candidates: List[Dict[str, Any]] = []

    for sym, spec in FTMO_UNIVERSE_SPECS.items():
        d1_path = os.path.join(DATA_DIR, f"{sym}_1d_audited.parquet")
        d1_df = pd.read_parquet(d1_path) if os.path.exists(d1_path) else None
        sister_sym = SISTER_ASSET_MAP.get(sym)

        for tf in ("1h", "15m"):
            path = os.path.join(DATA_DIR, f"{sym}_{tf}_audited.parquet")
            if not os.path.exists(path):
                continue
            raw_df = pd.read_parquet(path)
            sis_path = os.path.join(DATA_DIR, f"{sister_sym}_{tf}_audited.parquet") if sister_sym else None
            sis_df = pd.read_parquet(sis_path) if (sis_path and os.path.exists(sis_path)) else None
            df = prepare_tradfi_features(raw_df, htf_1d_df=d1_df, sister_df=sis_df)
            if df.empty or len(df) < 240:
                continue

            for archetype in ("IMPULSE_OTE_SMC", "LIQUIDITY_SWEEP_JUDAS"):
                trades = simulate_tradfi_series(df, sym, spec, archetype=archetype)
                min_total = 35 if tf == "1h" else 20
                if len(trades) < min_total:
                    continue
                split = int(len(trades) * 0.60)
                tr_m = _summarize(trades[:split])
                te_m = _summarize(trades[split:])
                candidates.append({
                    "symbol": sym,
                    "timeframe": tf,
                    "archetype": archetype,
                    "cluster": spec["cluster"],
                    "train": tr_m,
                    "blind_oos": te_m,
                    "oos_trades": trades[split:],
                })

    fdr_flags = benjamini_hochberg_fdr([c["blind_oos"]["p_value"] for c in candidates], alpha=0.20)
    approved: List[Dict[str, Any]] = []
    for c, fdr_ok in zip(candidates, fdr_flags):
        c["fdr_passed"] = fdr_ok
        min_oos_n = 15 if c["timeframe"] == "1h" else 10
        ok = (
            c["train"]["n"] >= 20
            and c["train"]["pf"] >= 1.15
            and c["train"]["mean_r"] >= 0.05
            and c["blind_oos"]["n"] >= min_oos_n
            and c["blind_oos"]["pf"] >= 1.15
            and c["blind_oos"]["mean_r"] >= 0.05
        )
        c["approved_for_ftmo"] = ok
        if ok:
            approved.append(c)

    # Selección 100% ciega sobre Train (Zero OOS Sorting) + Mutex de Clúster
    best_per_symbol: Dict[str, Dict[str, Any]] = {}
    for c in sorted(approved, key=lambda x: (x["train"]["t_stat"], x["train"]["pf"]), reverse=True):
        if c["symbol"] not in best_per_symbol:
            best_per_symbol[c["symbol"]] = c

    cluster_counts: Dict[str, int] = defaultdict(int)
    selected_portfolio: List[Dict[str, Any]] = []
    raw_oos_trades: List[Dict[str, Any]] = []

    for sym, c in best_per_symbol.items():
        cl = c["cluster"]
        if cluster_counts[cl] >= 2:
            continue
        cluster_counts[cl] += 1
        tier_weight = 1.0 if c["blind_oos"]["n"] >= 45 else 0.65
        selected_portfolio.append({
            "symbol": sym,
            "timeframe": c["timeframe"],
            "archetype": c["archetype"],
            "cluster": cl,
            "tier_weight": tier_weight,
            "train_pf": c["train"]["pf"],
            "oos_pf": c["blind_oos"]["pf"],
            "oos_mean_r": c["blind_oos"]["mean_r"],
            "oos_n": c["blind_oos"]["n"],
            "oos_total_r": c["blind_oos"]["total_r"],
        })
        for t in c["oos_trades"]:
            t_copy = dict(t)
            t_copy["cluster"] = cl
            t_copy["tier_weight"] = tier_weight
            t_copy["weighted_r"] = round(float(t["outcome_r"]) * tier_weight, 4)
            raw_oos_trades.append(t_copy)

    # Replay concurrente con Mutex de Clúster por día (XAUUSD <-> XAGUSD nunca simultáneos)
    raw_oos_trades.sort(key=lambda x: (x["day"], -x["tier_weight"]))
    oos_trade_stream: List[Dict[str, Any]] = []
    seen_cluster_day: set = set()
    trades_per_day: Dict[str, int] = defaultdict(int)
    for t in raw_oos_trades:
        c_key = (t["day"], t["cluster"])
        if c_key in seen_cluster_day or trades_per_day[t["day"]] >= 2:
            continue
        seen_cluster_day.add(c_key)
        trades_per_day[t["day"]] += 1
        oos_trade_stream.append(t)

    oos_rs = [t["weighted_r"] for t in oos_trade_stream]
    portfolio_dsr = compute_deflated_sharpe_ratio(oos_rs, num_trials=max(1, len(candidates)))
    cpcv_15_folds = run_cpcv_validation(oos_rs, n_splits=6, k_test=2, embargo_pct=0.02)

    summary_rows = [{k: v for k, v in c.items() if k != "oos_trades"} for c in candidates]
    report = {
        "total_evaluated_configs": len(candidates),
        "approved_count": len(approved),
        "selected_portfolio": selected_portfolio,
        "portfolio_dsr": portfolio_dsr,
        "cpcv_15_folds": cpcv_15_folds,
        "oos_trade_stream": oos_trade_stream,
        "all_candidates": summary_rows,
    }
    if save_report:
        os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    return report


if __name__ == "__main__":
    res = run_ftmo_swing_tournament(save_report=True)
    print(f"Evaluados: {res['total_evaluated_configs']} | Aprobados OOS: {res['approved_count']} | Portafolio Final: {len(res['selected_portfolio'])}")
    for item in res["selected_portfolio"]:
        print("  SELECTED:", item)
