"""
engine/backtest/test_elite_improvements_experiment.py
=====================================================
Auditoría Cuantitativa de las 3 Mejoras de Élite Institucional:
1. Triple-Screen Macro Confluence (1D -> 1h -> 15m)
2. Volatilidad Escalar en Dollar Risk (ATR-Normalized Sizing)
3. Order Flow Delta Convergence (Sidecar Tick CVD)

Ejecuta el Replay Histórico Cronológico de 180 días sobre el Universo Canónico Auditado (13 activos)
y somete cada variante a 10,000 caminos Monte Carlo para validar resiliencia estocástica.
"""

import sys
import os
import copy
import json
import numpy as np
import pandas as pd
from typing import Dict, List, Any

# Root path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from engine.backtest.unified_backtest_engine import (
    UnifiedBacktestEngine,
    MEGA_CAPS,
    HIGH_BETA_ALTS,
    TRADFI_METALS,
    DATA_DIR
)
from engine.indicators.volume import calculate_cvd_divergence, calculate_order_flow_delta
from engine.indicators.polars_engine import polars_engine
from engine.indicators.structure import identify_order_blocks
from engine.indicators.volume import calculate_vwap, calculate_session_anchored_vwap
from engine.risk.risk_manager import RiskManager
from engine.risk.cluster_risk_guard import cluster_risk_guard
from engine.core.tear_sheet import calculate_portfolio_metrics
from engine.analytics.monte_carlo_resilience_engine import MonteCarloResilienceEngine


class EliteImprovementsAuditor:
    """
    Auditor experimental para evaluar cuantitativamente las 3 mejoras.
    """

    def __init__(self):
        self.engine = UnifiedBacktestEngine()
        self.btc_map = self.engine._load_btc_macro_map()

    def run_experiment(
        self,
        enable_triple_screen: bool = False,
        enable_atr_normalized_sizing: bool = False,
        enable_cvd_convergence: bool = False,
        name: str = "BASELINE"
    ) -> Dict[str, Any]:
        """
        Ejecuta la cartera cronológica aplicando selectivamente las mejoras.
        """
        all_assets = MEGA_CAPS + HIGH_BETA_ALTS + TRADFI_METALS
        all_results = []
        seen = set()

        for sym in all_assets:
            if sym in seen or sym == "XAUUSDT":
                continue
            seen.add(sym)
            t_list = self._run_asset_with_features(
                sym,
                interval="15m",
                enable_triple_screen=enable_triple_screen,
                enable_cvd_convergence=enable_cvd_convergence
            )
            all_results.extend(t_list)

        # 1h Swing Elite (SOP-101)
        if all_results:
            min_15m_ts = min(pd.to_datetime(t["entry_time"]) for t in all_results)
            swing_1h_elite = ["XAUUSDT", "NEARUSDT", "ATOMUSDT", "ETHUSDT", "BTCUSDT", "INJUSDT", "LINKUSDT"]
            for sym_1h in swing_1h_elite:
                t_1h = self._run_asset_with_features(
                    sym_1h,
                    interval="1h",
                    enable_triple_screen=enable_triple_screen,
                    enable_cvd_convergence=enable_cvd_convergence
                )
                for tr_1h in t_1h:
                    if pd.to_datetime(tr_1h["entry_time"]) >= min_15m_ts:
                        all_results.append(tr_1h)

        df_all = pd.DataFrame(all_results)
        if df_all.empty:
            return {"name": name, "trades": 0}

        # Desempate cronológico
        def calc_priority(row):
            score = float(row.get("confluence_score", 70.0))
            s = str(row.get("symbol", "")).upper()
            mult = 1.25 if any(t in s for t in ("ETH", "SOL", "BNB", "INJ")) else (1.00 if any(t in s for t in ("AVAX", "NEAR", "SUI", "XRP", "BTC")) else 0.85)
            # Bonificación extra de prioridad si tiene Triple Screen
            if enable_triple_screen and row.get("triple_screen_aligned", False):
                mult *= 1.05
            return round(score * mult, 2)

        df_all["priority_score"] = df_all.apply(calc_priority, axis=1)
        df_all = df_all.sort_values(by=["entry_time", "priority_score"], ascending=[True, False]).reset_index(drop=True)

        # Simulación de Cartera Cronológica Event-Driven
        executed_trades = []
        active_positions = []
        active_unprotected = []
        compounding_cap = 1000.0
        max_comp_equity = 1000.0
        max_comp_dd = 0.0

        for idx, tr in df_all.iterrows():
            entry_dt = pd.to_datetime(tr["entry_time"])
            exit_dt = pd.to_datetime(tr["exit_time"])
            tp1_dt = pd.to_datetime(tr["tp1_time"]) if tr.get("tp1_time") else None
            risk_freed_dt = tp1_dt if tp1_dt else exit_dt
            sym = tr["symbol"]
            direction = tr["direction"]

            # Veto Macro BTC
            if sym not in ("BTCUSDT", "XAUUSDT", "PAXGUSDT"):
                btc_trend = self.btc_map.get(entry_dt, "NEUTRAL")
                aligned = (direction == "LONG" and btc_trend == "BULLISH") or (direction == "SHORT" and btc_trend == "BEARISH")
                if not aligned:
                    continue

            # Poda de activos excluidos
            if sym in ("RENDERUSDT", "AVAXUSDT"):
                continue

            # Horas tóxicas
            if entry_dt.hour in [10, 14]:
                continue

            # Limpiar posiciones
            active_unprotected = [p for p in active_unprotected if p["risk_freed_time"] > entry_dt]
            active_positions = [p for p in active_positions if p["exit_time"] > entry_dt]
            open_symbols = [p["symbol"] for p in active_positions]

            if sym in open_symbols:
                continue

            if len(active_positions) >= 4 or len(active_unprotected) >= 2:
                continue

            # Registrar
            pos_info = {"symbol": sym, "entry_time": entry_dt, "risk_freed_time": risk_freed_dt, "exit_time": exit_dt}
            active_positions.append(pos_info)
            if risk_freed_dt > entry_dt:
                active_unprotected.append(pos_info)

            # Sizing Base vs Alpha
            # Trinity Boost SOP-47
            is_kz = (7 <= entry_dt.hour <= 10) or (12 <= entry_dt.hour <= 15)
            trinity_mult = 1.35 if (sym in ("BNBUSDT", "SOLUSDT", "FETUSDT") and is_kz) else 1.0

            # Golden Hours SOP-49
            gh_mult = 1.20 if (8 <= entry_dt.hour <= 11) or (13 <= entry_dt.hour <= 16) else 1.0

            sizing_mult = trinity_mult * gh_mult

            # MEJORA 2: Volatilidad Escalar en Dollar Risk (ATR-Normalized)
            vol_scalar = 1.0
            if enable_atr_normalized_sizing:
                asset_atr_pct = float(tr.get("risk_pct", 1.20))
                # Benchmark normalizado en 1.20% (media de cartera)
                # Escalar inversamente: Si volatilidad sube mucho, reducir riesgo; si es muy baja y limpia, expandir moderadamente
                vol_scalar = float(np.clip(1.20 / max(0.40, asset_atr_pct), 0.75, 1.25))
                sizing_mult *= vol_scalar

            outcome_r = float(tr["outcome_r"])
            alpha_r = outcome_r * sizing_mult

            # Compounding
            risk_usd = compounding_cap * 0.025 * (vol_scalar if enable_atr_normalized_sizing else 1.0)
            trade_pnl_usd = outcome_r * risk_usd * min(sizing_mult, 1.50)
            compounding_cap = max(100.0, compounding_cap + trade_pnl_usd)
            if compounding_cap > max_comp_equity:
                max_comp_equity = compounding_cap
            cur_dd = (max_comp_equity - compounding_cap) / max_comp_equity * 100.0
            if cur_dd > max_comp_dd:
                max_comp_dd = cur_dd

            executed_trades.append({
                "symbol": sym,
                "entry_time": entry_dt,
                "direction": direction,
                "outcome_r": outcome_r,
                "alpha_r": alpha_r,
                "sizing_mult": sizing_mult,
                "playbook": tr["playbook"],
                "triple_screen": tr.get("triple_screen_aligned", False),
                "cvd_status": tr.get("cvd_status", "NEUTRAL")
            })

        if not executed_trades:
            return {"name": name, "trades": 0}

        df_exec = pd.DataFrame(executed_trades)
        total_trades = len(df_exec)
        winners = df_exec[df_exec["outcome_r"] > 0]
        losers = df_exec[df_exec["outcome_r"] < 0]
        wr = (len(winners) / total_trades) * 100.0

        total_r_base = float(df_exec["outcome_r"].sum())
        total_r_alpha = float(df_exec["alpha_r"].sum())

        gp_base = float(winners["outcome_r"].sum()) if len(winners) > 0 else 0.0
        gl_base = abs(float(losers["outcome_r"].sum())) if len(losers) > 0 else 1.0
        pf_base = gp_base / gl_base if gl_base > 0 else 99.0

        gp_alpha = float(winners["alpha_r"].sum()) if len(winners) > 0 else 0.0
        gl_alpha = abs(float(losers["alpha_r"].sum())) if len(losers) > 0 else 1.0
        pf_alpha = gp_alpha / gl_alpha if gl_alpha > 0 else 99.0

        # Drawdowns en R
        equity_base = df_exec["outcome_r"].cumsum()
        peak_base = equity_base.cummax()
        max_dd_base_r = abs(float((equity_base - peak_base).min()))

        equity_alpha = df_exec["alpha_r"].cumsum()
        peak_alpha = equity_alpha.cummax()
        max_dd_alpha_r = abs(float((equity_alpha - peak_alpha).min()))

        metrics = calculate_portfolio_metrics(df_exec["alpha_r"].tolist())

        # Monte Carlo Simulation (10,000 caminos)
        mc_engine = MonteCarloResilienceEngine(audited_returns=df_exec["alpha_r"].tolist())
        mc_res = mc_engine.run_simulation(iterations=10000, horizon_trades=100, seed=42)

        return {
            "name": name,
            "total_trades": total_trades,
            "win_rate": round(wr, 2),
            "total_r_base": round(total_r_base, 2),
            "total_r_alpha": round(total_r_alpha, 2),
            "pf_base": round(pf_base, 2),
            "pf_alpha": round(pf_alpha, 2),
            "max_dd_base_r": round(max_dd_base_r, 2),
            "max_dd_alpha_r": round(max_dd_alpha_r, 2),
            "sharpe_ratio": round(metrics.get("sharpe_ratio", 0.0), 2),
            "sortino_ratio": round(metrics.get("sortino_ratio", 0.0), 2),
            "expectancy_r": round(metrics.get("expectancy_r", 0.0), 3),
            "compounding_final_usd": round(compounding_cap, 2),
            "compounding_roi_pct": round(((compounding_cap - 1000.0) / 1000.0) * 100.0, 1),
            "compounding_max_dd": round(max_comp_dd, 2),
            "mc_var_99_r": round(mc_res.var_99_r, 2),
            "mc_cvar_99_r": round(mc_res.cvar_99_r, 2),
            "mc_p95_max_dd_r": round(mc_res.p95_max_drawdown_r, 2),
            "mc_risk_of_ruin_pct": round(mc_res.risk_of_ruin_pct, 2),
            "mc_probability_of_profit_pct": round(mc_res.probability_of_profit_pct, 2)
        }

    def _run_asset_with_features(
        self,
        symbol: str,
        interval: str,
        enable_triple_screen: bool,
        enable_cvd_convergence: bool
    ) -> List[Dict[str, Any]]:
        """
        Ejecuta la extracción de setups de un activo incorporando las mejoras.
        """
        # Cargar datos
        target_file = None
        data_candidates = [symbol]
        if symbol in ("XAUUSDT", "PAXGUSDT", "XAUUSD"):
            data_candidates = ["PAXGUSDT", "XAUUSD", "XAUUSDT"]

        for s_cand in data_candidates:
            f_180 = os.path.join(DATA_DIR, f"{s_cand}_{interval}_180d.parquet")
            f_aud = os.path.join(DATA_DIR, f"{s_cand}_{interval}_audited.parquet")
            if os.path.exists(f_180):
                target_file = f_180
                break
            elif os.path.exists(f_aud):
                target_file = f_aud
                break

        if not target_file:
            f15 = os.path.join(DATA_DIR, f"{symbol}_15m_180d.parquet")
            if not os.path.exists(f15):
                return []
            raw = pd.read_parquet(f15)
            raw.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume", "t": "timestamp"}, inplace=True)
            if not pd.api.types.is_datetime64_any_dtype(raw["timestamp"]):
                first_ts = float(raw["timestamp"].iloc[0])
                unit = "s" if first_ts < 1e11 else "ms"
                raw["timestamp"] = pd.to_datetime(raw["timestamp"], unit=unit)
            raw.set_index("timestamp", inplace=True)
            rule = "1h" if interval in ["1h", "1H", "60m"] else "1D"
            df = raw.resample(rule).agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna().reset_index()
        else:
            raw = pd.read_parquet(target_file)
            raw.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume", "t": "timestamp"}, inplace=True)
            if not pd.api.types.is_datetime64_any_dtype(raw["timestamp"]):
                first_ts = float(raw["timestamp"].iloc[0])
                unit = "s" if first_ts < 1e11 else "ms"
                raw["timestamp"] = pd.to_datetime(raw["timestamp"], unit=unit)
            df = raw.sort_values("timestamp").reset_index(drop=True)

        if getattr(df["timestamp"].dt, "tz", None) is not None:
            df["timestamp"] = df["timestamp"].dt.tz_localize(None)

        if len(df) < 100:
            return []

        # Indicadores
        df = polars_engine.compute_indicators(df)
        df = identify_order_blocks(df)
        df = self.engine.strategy.analyze(df, interval=interval)

        # 1h EMA200 (en 15m son 800 velas; en 1h son 200 velas)
        df["ema_htf"] = df["close"].ewm(span=800 if interval == "15m" else 200).mean()

        # MEJORA 1: Media Diaria de Tendencia Macro (1D EMA50)
        daily_span = 1920 if interval == "15m" else 480
        df["ema_daily_macro"] = df["close"].ewm(span=daily_span).mean()

        df["vol_sma"] = df["volume"].rolling(20).mean()
        df["rvol"] = df["volume"] / (df["vol_sma"] + 1e-9)
        change = (df["close"] - df["close"].shift(10)).abs()
        vol = (df["close"] - df["close"].shift(1)).abs().rolling(10).sum()
        df["ker_fractal"] = (change / (vol + 1e-9)).fillna(0.5)
        df = calculate_vwap(df)
        df = calculate_session_anchored_vwap(df)

        trades = []
        n = len(df)
        last_trade_exit_idx = -1

        for i in range(50, n - 25):
            if i <= last_trade_exit_idx:
                continue

            row = df.iloc[i]
            dt = row["timestamp"]
            hour = dt.hour

            if not self.engine.is_trade_allowed_sop18(symbol, dt):
                continue

            if self.engine.strict_killzones:
                if not (7 <= hour <= 12 or 13 <= hour <= 17):
                    continue

            ker_val = float(row.get("ker", 0.5))
            rvol_val = float(row.get("rvol", 1.0))
            if ker_val < 0.35 or rvol_val < 1.10:
                continue

            c = float(row["close"])
            ema_htf = float(row["ema_htf"])
            ema_daily = float(row["ema_daily_macro"])
            atr = float(row["atr"]) if "atr" in row and row["atr"] > 0 else (c * 0.005)

            if c < 0.10:
                continue

            adx_val = float(row.get("adx", 25.0))
            is_regime_ok, _ = RiskManager.check_regime_quarantine(adx_val, ker_val)
            if not is_regime_ok:
                continue

            is_bull_htf = c > ema_htf
            is_bear_htf = c < ema_htf

            has_bull = bool(row.get("recent_ob_bull", False)) and (bool(row.get("recent_fvg_bull", False)) or bool(row.get("recent_sweep_bull", False))) and is_bull_htf
            has_bear = bool(row.get("recent_ob_bear", False)) and (bool(row.get("recent_fvg_bear", False)) or bool(row.get("recent_sweep_bear", False))) and is_bear_htf

            if not (has_bull or has_bear):
                continue

            direction = "LONG" if has_bull else "SHORT"

            # ── MEJORA 1: TRIPLE-SCREEN MACRO CONFLUENCE ──
            # Alineación de 1D: c > ema_daily para Long, c < ema_daily para Short
            is_daily_aligned = (c > ema_daily) if direction == "LONG" else (c < ema_daily)
            confluence_score = 75
            if enable_triple_screen:
                if is_daily_aligned:
                    confluence_score += 5  # Bonificación +5.0 pts
                else:
                    # Si va en contra de la tendencia diaria macro, exigir mayor KER para filtrar ruido
                    if ker_val < 0.45:
                        continue

            # SOP-27 VWAP & SOP-95 AVWAP
            vwap_dist = float(row.get("vwap_dist_pct", 0.0))
            is_vwap_ok, _ = RiskManager.check_vwap_exhaustion(direction, vwap_dist)
            if not is_vwap_ok:
                continue

            session_avwap_dist = float(row.get("session_avwap_dist_pct", 0.0))
            if direction == "LONG" and session_avwap_dist < -0.40:
                continue
            elif direction == "SHORT" and session_avwap_dist > 0.40:
                continue

            # ── MEJORA 3: ORDER FLOW DELTA / CVD CONVERGENCE ──
            cvd_status = "IN_SYNC"
            if enable_cvd_convergence and i >= 30:
                slice_df = df.iloc[max(0, i-30):i+1]
                cvd_eval = calculate_cvd_divergence(slice_df, window=min(30, len(slice_df)))
                cvd_status = cvd_eval.get("status", "IN_SYNC")

                # Veto si CVD diverge agresivamente EN CONTRA
                if direction == "LONG" and cvd_status == "BEARISH_DIVERGENCE":
                    continue
                elif direction == "SHORT" and cvd_status == "BULLISH_DIVERGENCE":
                    continue
                elif (direction == "LONG" and cvd_status == "BULLISH_DIVERGENCE") or (direction == "SHORT" and cvd_status == "BEARISH_DIVERGENCE"):
                    confluence_score += 5

            # Entradas y SL
            if direction == "LONG":
                entry = c - (atr * 0.35)
                sl = entry - (atr * 0.85)
                risk = entry - sl
                p_tp1 = entry + (risk * 1.2)
                p_tp2 = entry + (risk * 2.0)
                p_tp3 = entry + (risk * 3.5)
            else:
                entry = c + (atr * 0.35)
                sl = entry + (atr * 0.85)
                risk = sl - entry
                p_tp1 = entry - (risk * 1.2)
                p_tp2 = entry - (risk * 2.0)
                p_tp3 = entry - (risk * 3.5)

            if risk <= 0 or (risk / entry) > 0.05:
                continue

            # Check fill
            filled = False
            fill_idx = -1
            for j in range(i + 1, min(i + 9, n)):
                bh, bl = float(df.iloc[j]["high"]), float(df.iloc[j]["low"])
                if direction == "LONG" and bl <= entry:
                    filled = True
                    fill_idx = j
                    break
                elif direction == "SHORT" and bh >= entry:
                    filled = True
                    fill_idx = j
                    break

            if not filled:
                continue

            # Simulación MFE Harvesting Grid (50/30/20)
            hit_tp1 = False
            hit_tp2 = False
            tp1_idx = None
            curr_sl = sl
            outcome_r = 0.0
            close_reason = ""
            rem_pos = 1.0

            max_horizon = min(fill_idx + (48 if interval == "15m" else 36), n)
            exit_idx = fill_idx

            for k in range(fill_idx + 1, max_horizon):
                bar = df.iloc[k]
                bh = float(bar["high"])
                bl = float(bar["low"])
                exit_idx = k

                if direction == "LONG":
                    cur_adverse = (entry - bl) / risk
                    if cur_adverse >= 0.65 and not hit_tp1:
                        close_reason = "SOP25_EARLY_INVALIDATION"
                        outcome_r -= (0.65 * rem_pos)
                        break

                    if bl <= curr_sl:
                        if curr_sl == sl:
                            close_reason = "STOP_LOSS"
                            outcome_r -= (1.0 * rem_pos)
                        else:
                            close_reason = "PROTECTED_EXIT"
                            if hit_tp2:
                                lock_r = (curr_sl - entry) / risk
                                if lock_r > 0:
                                    outcome_r += (lock_r * rem_pos)
                        break

                    if not hit_tp1 and bh >= p_tp1:
                        hit_tp1 = True
                        tp1_idx = k
                        outcome_r += (1.2 * 0.50)
                        rem_pos -= 0.50
                        curr_sl = entry + (entry * 0.0008)

                    if hit_tp1 and not hit_tp2 and bh >= p_tp2:
                        hit_tp2 = True
                        outcome_r += (2.0 * 0.30)
                        rem_pos -= 0.30
                        curr_sl = entry + (risk * 1.0)

                    if hit_tp2 and bh >= p_tp3:
                        outcome_r += (3.5 * rem_pos)
                        rem_pos = 0.0
                        close_reason = "TP3_FULL_TARGET"
                        break
                else:  # SHORT
                    cur_adverse = (bh - entry) / risk
                    if cur_adverse >= 0.65 and not hit_tp1:
                        close_reason = "SOP25_EARLY_INVALIDATION"
                        outcome_r -= (0.65 * rem_pos)
                        break

                    if bh >= curr_sl:
                        if curr_sl == sl:
                            close_reason = "STOP_LOSS"
                            outcome_r -= (1.0 * rem_pos)
                        else:
                            close_reason = "PROTECTED_EXIT"
                            if hit_tp2:
                                lock_r = (entry - curr_sl) / risk
                                if lock_r > 0:
                                    outcome_r += (lock_r * rem_pos)
                        break

                    if not hit_tp1 and bl <= p_tp1:
                        hit_tp1 = True
                        tp1_idx = k
                        outcome_r += (1.2 * 0.50)
                        rem_pos -= 0.50
                        curr_sl = entry - (entry * 0.0008)

                    if hit_tp1 and not hit_tp2 and bl <= p_tp2:
                        hit_tp2 = True
                        outcome_r += (2.0 * 0.30)
                        rem_pos -= 0.30
                        curr_sl = entry - (risk * 1.0)

                    if hit_tp2 and bl <= p_tp3:
                        outcome_r += (3.5 * rem_pos)
                        rem_pos = 0.0
                        close_reason = "TP3_FULL_TARGET"
                        break

            # Comisiones
            fee_friction_r = (0.0002 + 0.0006 + 0.0002) * 15 * 0.5
            net_outcome_r = outcome_r - (fee_friction_r if outcome_r != 0 else 0.0)

            # Playbook
            if bool(row.get("recent_sweep_bull", False)) or bool(row.get("recent_sweep_bear", False)):
                playbook = "LIQUIDITY_SWEEP_FVG"
            elif bool(row.get("recent_ob_bull", False)) or bool(row.get("recent_ob_bear", False)):
                playbook = "OB_DISCOUNT_RETEST"
            elif ker_val >= 0.50:
                playbook = "BOS_MOMENTUM_EXPANSION"
            else:
                playbook = "TREND_CONTINUATION_EMA"

            trades.append({
                "symbol": symbol,
                "interval": interval,
                "playbook": playbook,
                "entry_time": str(df.iloc[fill_idx]["timestamp"]),
                "exit_time": str(df.iloc[exit_idx]["timestamp"]),
                "tp1_time": str(df.iloc[tp1_idx]["timestamp"]) if hit_tp1 and tp1_idx is not None else None,
                "direction": direction,
                "entry": entry,
                "sl": sl,
                "confluence_score": confluence_score,
                "triple_screen_aligned": is_daily_aligned,
                "cvd_status": cvd_status,
                "risk_pct": round((risk / entry) * 100, 2),
                "outcome_r": round(net_outcome_r, 2),
                "close_reason": close_reason or ("EXPIRED_HORIZON" if outcome_r >= 0 else "STOP_LOSS")
            })
            last_trade_exit_idx = exit_idx

        return trades


def run_full_comparison_matrix():
    print("=" * 95)
    print("🔬 MATRIZ DE AUDITORÍA COMPARATIVA: 3 MEJORAS DE ÉLITE EN BACKTEST & MONTE CARLO")
    print("=" * 95)
    auditor = EliteImprovementsAuditor()

    # 1. Config A: Baseline
    print("\n[1/5] Evaluando Config A: BASELINE ACTUAL...")
    res_a = auditor.run_experiment(
        enable_triple_screen=False,
        enable_atr_normalized_sizing=False,
        enable_cvd_convergence=False,
        name="A: Baseline Actual"
    )

    # 2. Config B: Triple Screen Confluence
    print("[2/5] Evaluando Config B: + TRIPLE-SCREEN MACRO (1D -> 1h -> 15m)...")
    res_b = auditor.run_experiment(
        enable_triple_screen=True,
        enable_atr_normalized_sizing=False,
        enable_cvd_convergence=False,
        name="B: + Triple-Screen 1D"
    )

    # 3. Config C: ATR-Normalized Sizing
    print("[3/5] Evaluando Config C: + VOLATILIDAD ESCALAR (ATR-Normalized Sizing)...")
    res_c = auditor.run_experiment(
        enable_triple_screen=False,
        enable_atr_normalized_sizing=True,
        enable_cvd_convergence=False,
        name="C: + Volatilidad Escalar"
    )

    # 4. Config D: Order Flow CVD Convergence
    print("[4/5] Evaluando Config D: + ORDER FLOW DELTA (CVD Convergence)...")
    res_d = auditor.run_experiment(
        enable_triple_screen=False,
        enable_atr_normalized_sizing=False,
        enable_cvd_convergence=True,
        name="D: + Order Flow CVD"
    )

    # 5. Config E: Trifecta Combinada
    print("[5/5] Evaluando Config E: APEX TRIFECTA (Triple-Screen + ATR-Sizing + CVD)...")
    res_e = auditor.run_experiment(
        enable_triple_screen=True,
        enable_atr_normalized_sizing=True,
        enable_cvd_convergence=True,
        name="E: APEX TRIFECTA (A+B+C+D)"
    )

    results = [res_a, res_b, res_c, res_d, res_e]

    print("\n" + "=" * 115)
    print(f"{'Configuración':<26} | {'Trades':<6} | {'WR%':<6} | {'Total R (Base/Alpha)':<20} | {'Profit Factor':<13} | {'Max DD':<9} | {'Sharpe':<6} | {'ROI Bitunix':<12} | {'MC VaR99':<8}")
    print("-" * 115)
    for r in results:
        tot_r_str = f"{r['total_r_base']:>+6.1f}R / {r['total_r_alpha']:>+6.1f}R"
        pf_str = f"{r['pf_base']:.2f} / {r['pf_alpha']:.2f}"
        dd_str = f"-{r['max_dd_alpha_r']:.1f}R"
        roi_str = f"+{r['compounding_roi_pct']:,.0f}%"
        var_str = f"{r['mc_var_99_r']:>+5.1f}R"
        print(f"{r['name']:<26} | {r['total_trades']:<6} | {r['win_rate']:>5.1f}% | {tot_r_str:<20} | {pf_str:<13} | {dd_str:<9} | {r['sharpe_ratio']:>6.2f} | {roi_str:<12} | {var_str:<8}")
    print("=" * 115)

    out_file = os.path.join(DATA_DIR, "elite_improvements_comparison_results.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)
    print(f"📊 Resultados detallados exportados a: {out_file}\n")
    return results


if __name__ == "__main__":
    run_full_comparison_matrix()
