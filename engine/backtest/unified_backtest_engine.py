"""
engine/backtest/unified_backtest_engine.py
=============================================================================
SLINGSHOT APEX v37.0 — QUANTUM REPLAY ENGINE (CLEAN SSoT, SOP-25 & SOP-26)
=============================================================================
Única Fuente de la Verdad (Single Source of Truth) para la auditoría cuantitativa.

Mecánica Cuantitativa Institucional v37.0 (SOP-25 Early Invalidation & SOP-26 MFE Harvesting):
1. Detección Vectorizada de Order Blocks y FVGs en Rust (Polars Engine).
2. Alineación de Tendencia HTF (1H EMA200 / 15m EMA800).
3. Filtro Cuántico de Ventanas Temporales Específico por Activo (SOP-18).
4. Entradas Límite SMC en zona de descuento FVG (40%-50% retracement).
5. [SOP-25] Early Structural Invalidation a -0.65R (ahorro de +0.35R por perdedor).
6. [SOP-26] Dynamic MFE Harvesting Grid (40% en +1.2R, 40% en +2.0R, 20% Runner en +3.5R).
7. [SOP-26] Bloqueo en Verde de +1.0R neto al tocar +2.0R (captura antes de retrocesos a BE).
8. [SOP-21] Apalancamiento Seguro Dinámico y Descuento Real de Comisiones Bitunix.
"""

import sys
import os
import glob
import json
import argparse
from datetime import datetime
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Path config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from engine.indicators.polars_engine import polars_engine
from engine.indicators.structure import identify_order_blocks
from engine.indicators.volume import calculate_vwap
from engine.strategies.smc import SMCInstitutionalStrategy
from engine.core.confluence import confluence_manager
from engine.risk.risk_manager import RiskManager
from engine.core.logger import logger

logger.setLevel("ERROR")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

MEGA_CAPS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "AVAXUSDT", "LINKUSDT"]
HIGH_BETA_ALTS = ["INJUSDT", "BNBUSDT", "NEARUSDT", "FETUSDT", "SUIUSDT", "RENDERUSDT", "ATOMUSDT"]


class UnifiedBacktestEngine:
    """
    [TITAN REPLAY ENGINE v31.0]
    Motor de Replay Histórico 100% fiel al comportamiento del live engine.
    """

    def __init__(
        self,
        account_balance: float = 100_000.0,
        risk_per_trade_pct: float = 0.01,
        maker_fee: float = 0.0002,
        taker_fee: float = 0.0006,
        slippage: float = 0.0002,
        min_confluence_score: int = 50,
        strict_killzones: bool = True
    ):
        self.initial_balance = account_balance
        self.current_balance = account_balance
        self.risk_pct = risk_per_trade_pct
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee
        self.slippage = slippage
        self.min_score = min_confluence_score
        self.strict_killzones = strict_killzones
        self.strategy = SMCInstitutionalStrategy()
        self.risk_mgr = RiskManager(account_balance=account_balance, base_risk_pct=risk_per_trade_pct)

    def _load_btc_macro_map(self) -> Dict[Any, str]:
        """Carga la brújula macro de Bitcoin."""
        btc_file = os.path.join(DATA_DIR, "BTCUSDT_15m_180d.parquet")
        if not os.path.exists(btc_file):
            return {}
        try:
            df_btc = pd.read_parquet(btc_file)
            df_btc.columns = [str(c).lower() for c in df_btc.columns]
            ts_col = "timestamp" if "timestamp" in df_btc.columns else "t"
            df_btc["dt"] = pd.to_datetime(df_btc[ts_col], unit="s" if float(df_btc[ts_col].iloc[0]) < 1e11 else "ms")
            df_btc["ema200"] = df_btc["close"].ewm(span=200, adjust=False).mean()
            df_btc["trend"] = np.where(df_btc["close"] > df_btc["ema200"], "BULLISH", "BEARISH")
            return dict(zip(df_btc["dt"], df_btc["trend"]))
        except Exception:
            return {}

    def is_trade_allowed_sop18(self, symbol: str, dt: datetime) -> bool:
        """
        Protocolo de Seguridad SOP-18: Time-Gating Dinámico Específico por Activo.
        """
        d = dt.day_name() if hasattr(dt, "day_name") else pd.to_datetime(dt).day_name()
        h = dt.hour

        # 1. Reglas Globales de Protección
        if d == "Monday" and h <= 13: return False
        if d == "Thursday" and h >= 16: return False
        if h == 18: return False

        # 2. Regla Específica AVAXUSDT: Solo ventanas 09:00 y 17:00 UTC
        if symbol == "AVAXUSDT":
            return h in [9, 17] and d in ["Tuesday", "Wednesday", "Thursday", "Saturday"]

        # 3. Regla Específica RENDERUSDT: Solo ventanas 08:00, 13:00, 17:00 y 18:00 UTC
        if symbol == "RENDERUSDT":
            return h in [8, 13, 17, 18]

        # 4. Resto de Activos (Líderes): Pausa en apertura 13h excepto Miércoles
        if h == 13 and d != "Wednesday":
            return False

        return True

    def run_single_asset(
        self,
        symbol: str,
        interval: str = "15m",
        btc_map: dict = None,
        enable_elastic_runner: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Ejecuta la simulación cuantitativa institucional v31.0.
        """
        target_file = None
        f_180 = os.path.join(DATA_DIR, f"{symbol}_{interval}_180d.parquet")
        f_aud = os.path.join(DATA_DIR, f"{symbol}_{interval}_audited.parquet")
        
        if os.path.exists(f_180):
            target_file = f_180
        elif os.path.exists(f_aud):
            target_file = f_aud
        else:
            file_candidates = glob.glob(os.path.join(DATA_DIR, f"{symbol}_{interval}_*.parquet"))
            if file_candidates:
                target_file = file_candidates[0]

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
            rule = "1h" if interval in ["1h", "1H", "60m"] else ("4h" if interval == "4h" else "1D")
            df = raw.resample(rule).agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna().reset_index()
        else:
            raw = pd.read_parquet(target_file)
            raw.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume", "t": "timestamp"}, inplace=True)
            if not pd.api.types.is_datetime64_any_dtype(raw["timestamp"]):
                first_ts = float(raw["timestamp"].iloc[0])
                unit = "s" if first_ts < 1e11 else "ms"
                raw["timestamp"] = pd.to_datetime(raw["timestamp"], unit=unit)
            df = raw.sort_values("timestamp").reset_index(drop=True)

        if len(df) < 60:
            return []

        # 1. Indicadores Vectorizados en Rust + Estructura SMC
        df = polars_engine.compute_indicators(df)
        df = identify_order_blocks(df)
        df = self.strategy.analyze(df, interval=interval)

        # Tendencia HTF (Alineación 1H EMA200)
        df["ema_htf"] = df["close"].ewm(span=800).mean()

        # Filtros de Eficiencia y Microestructura
        df["vol_sma"] = df["volume"].rolling(20).mean()
        df["rvol"] = df["volume"] / (df["vol_sma"] + 1e-9)
        change = (df["close"] - df["close"].shift(10)).abs()
        vol = (df["close"] - df["close"].shift(1)).abs().rolling(10).sum()
        df["ker"] = change / (vol + 1e-9)
        df = calculate_vwap(df)

        trades = []
        n = len(df)
        last_trade_exit_idx = -1

        for i in range(50, n - 25):
            if i <= last_trade_exit_idx:
                continue

            row = df.iloc[i]
            dt = row["timestamp"]
            hour = dt.hour

            # Protocolo de Seguridad SOP-18: Time-Gating Específico por Activo
            if not self.is_trade_allowed_sop18(symbol, dt):
                continue

            # Filtro Horario (Killzones en 15m)
            if self.strict_killzones:
                if not (7 <= hour <= 12 or 13 <= hour <= 17):
                    continue

            # Filtro KER Antiruido y RVOL
            ker_val = float(row.get("ker", 0.5))
            rvol_val = float(row.get("rvol", 1.0))
            if ker_val < 0.35 or rvol_val < 1.10:
                continue

            # Veto Macro BTC
            btc_trend = btc_map.get(dt, "NEUTRAL") if btc_map else "NEUTRAL"
            if symbol == "PAXGUSDT" and btc_trend == "BEARISH":
                continue

            c = float(row["close"])
            ema_htf = float(row["ema_htf"])
            atr = float(row["atr"]) if "atr" in row and row["atr"] > 0 else (c * 0.005)

            # SOP-28: Quality Gate (Veto a micro-tokens con precio < $0.10)
            if c < 0.10:
                continue

            # SOP-31: Regime Quarantine (Anti-Chop: ADX < 18 y KER < 0.28)
            adx_val = float(row.get("adx", 25.0))
            is_regime_ok, _ = RiskManager.check_regime_quarantine(adx_val, ker_val)
            if not is_regime_ok:
                continue

            # Alineación Direccional HTF
            is_bull_htf = c > ema_htf
            is_bear_htf = c < ema_htf

            has_bull = bool(row.get("recent_ob_bull", False)) and (bool(row.get("recent_fvg_bull", False)) or bool(row.get("recent_sweep_bull", False))) and is_bull_htf
            has_bear = bool(row.get("recent_ob_bear", False)) and (bool(row.get("recent_fvg_bear", False)) or bool(row.get("recent_sweep_bear", False))) and is_bear_htf

            if not (has_bull or has_bear):
                continue

            direction = "LONG" if has_bull else "SHORT"

            # ── PROTOCOLO SOP-27: DAILY VWAP EXHAUSTION SHIELD ──
            vwap_dist = float(row.get("vwap_dist_pct", 0.0))
            is_vwap_ok, _ = RiskManager.check_vwap_exhaustion(direction, vwap_dist)
            if not is_vwap_ok:
                continue

            # 2. Entrada Límite en Descuento OTE / FVG (SOP-26 Grid 40/40/20 & SOP-48 Elastic Runner)
            ker_val = float(row.get("ker", 0.0))
            is_elastic = False
            target_tp3_r = 3.5
            if enable_elastic_runner and ker_val >= 0.50:
                is_elastic = True
                target_tp3_r = 5.0

            if direction == "LONG":
                entry = c - (atr * 0.35)
                sl = entry - (atr * 0.85)
                risk = entry - sl
                p_tp1 = entry + (risk * 1.2)   # TP1 (+1.2R, 40% + Fast BE)
                p_tp2 = entry + (risk * 2.0)   # TP2 (+2.0R, 40% + Bloqueo +1.0R en verde)
                p_tp3 = entry + (risk * target_tp3_r)   # TP3 Runner (+3.5R o +5.0R)
            else:
                entry = c + (atr * 0.35)
                sl = entry + (atr * 0.85)
                risk = sl - entry
                p_tp1 = entry - (risk * 1.2)
                p_tp2 = entry - (risk * 2.0)
                p_tp3 = entry - (risk * target_tp3_r)

            if risk <= 0 or (risk / entry) > 0.05:
                continue

            # Verificación de Activación de Orden Límite (hasta 8 velas)
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

            # 3. Simulación Walk-Forward con Modelo Cuántico v37.0 (SOP-25 & SOP-26 & SOP-48)
            hit_tp1 = False
            hit_tp2 = False
            tp1_idx = None
            tp2_idx = None
            curr_sl = sl
            outcome_r = 0.0
            close_reason = ""
            rem_pos = 1.0
            total_multiplier = 1.0

            max_horizon = min(fill_idx + (48 if interval == "15m" else 36), n)
            exit_idx = fill_idx

            for k in range(fill_idx + 1, max_horizon):
                bar = df.iloc[k]
                bh = float(bar["high"])
                bl = float(bar["low"])
                exit_idx = k

                if direction == "LONG":
                    # SOP-25: Early Structural Invalidation (@ -0.65R)
                    cur_adverse = (entry - bl) / risk
                    if cur_adverse >= 0.65 and not hit_tp1:
                        close_reason = "SOP25_EARLY_INVALIDATION"
                        outcome_r -= (0.65 * rem_pos * total_multiplier)
                        break

                    # Stop Loss Normal o Salida Protegida
                    if bl <= curr_sl:
                        if curr_sl == sl:
                            close_reason = "STOP_LOSS"
                            outcome_r -= (1.0 * rem_pos * total_multiplier)
                        else:
                            close_reason = "PROTECTED_EXIT"
                            if hit_tp2:
                                # Capturar la ganancia bloqueada en verde del runner (ej: +1.0R o +2.5R Ratchet)
                                lock_r = (curr_sl - entry) / risk
                                if lock_r > 0:
                                    outcome_r += (lock_r * rem_pos * total_multiplier)
                        break

                    # TP1 (+1.2R): Cobra 40% y mueve SL a Breakeven + Fee Buffer
                    if not hit_tp1 and bh >= p_tp1:
                        hit_tp1 = True
                        tp1_idx = k
                        outcome_r += (1.2 * 0.40 * total_multiplier)
                        rem_pos -= 0.40
                        curr_sl = entry + (entry * 0.0008)

                    # TP2 (+2.0R): Cobra 40% y sube SL a +1.0R en verde garantizado
                    if hit_tp1 and not hit_tp2 and bh >= p_tp2:
                        hit_tp2 = True
                        tp2_idx = k
                        outcome_r += (2.0 * 0.40 * total_multiplier)
                        rem_pos -= 0.40
                        curr_sl = entry + (risk * 1.0)

                    # SOP-48: Dynamic Elastic Ratchet Lock (@ +3.5R -> Stop a +2.5R)
                    if hit_tp2 and is_elastic:
                        if bh >= (entry + risk * 3.5):
                            ratchet_sl = entry + (risk * 2.5)
                            if ratchet_sl > curr_sl:
                                curr_sl = ratchet_sl

                    # TP3 (+3.5R o +5.0R): Cierra el 20% Runner final
                    if hit_tp2 and bh >= p_tp3:
                        outcome_r += (target_tp3_r * rem_pos * total_multiplier)
                        rem_pos = 0.0
                        close_reason = "TP3_FULL_TARGET"
                        break

                else:  # SHORT
                    # SOP-25: Early Structural Invalidation (@ -0.65R)
                    cur_adverse = (bh - entry) / risk
                    if cur_adverse >= 0.65 and not hit_tp1:
                        close_reason = "SOP25_EARLY_INVALIDATION"
                        outcome_r -= (0.65 * rem_pos * total_multiplier)
                        break

                    if bh >= curr_sl:
                        if curr_sl == sl:
                            close_reason = "STOP_LOSS"
                            outcome_r -= (1.0 * rem_pos * total_multiplier)
                        else:
                            close_reason = "PROTECTED_EXIT"
                            if hit_tp2:
                                lock_r = (entry - curr_sl) / risk
                                if lock_r > 0:
                                    outcome_r += (lock_r * rem_pos * total_multiplier)
                        break

                    # TP1 (+1.2R): Cobra 40% y mueve SL a Breakeven + Fee Buffer
                    if not hit_tp1 and bl <= p_tp1:
                        hit_tp1 = True
                        tp1_idx = k
                        outcome_r += (1.2 * 0.40 * total_multiplier)
                        rem_pos -= 0.40
                        curr_sl = entry - (entry * 0.0008)

                    # TP2 (+2.0R): Cobra 40% y sube SL a +1.0R en verde garantizado
                    if hit_tp1 and not hit_tp2 and bl <= p_tp2:
                        hit_tp2 = True
                        tp2_idx = k
                        outcome_r += (2.0 * 0.40 * total_multiplier)
                        rem_pos -= 0.40
                        curr_sl = entry - (risk * 1.0)

                    # SOP-48: Dynamic Elastic Ratchet Lock (@ -3.5R -> Stop a -2.5R)
                    if hit_tp2 and is_elastic:
                        if bl <= (entry - risk * 3.5):
                            ratchet_sl = entry - (risk * 2.5)
                            if ratchet_sl < curr_sl:
                                curr_sl = ratchet_sl

                    # TP3 (+3.5R o +5.0R): Cierra el 20% Runner final
                    if hit_tp2 and bl <= p_tp3:
                        outcome_r += (target_tp3_r * rem_pos * total_multiplier)
                        rem_pos = 0.0
                        close_reason = "TP3_FULL_TARGET"
                        break

            # Descuento exacto de comisiones y fricción con Apalancamiento Seguro SOP-21
            safe_lev = RiskManager.calculate_safe_leverage(entry, sl, max_cap=20)
            nominal_leverage = min(safe_lev, 20)
            fee_friction_r = (self.maker_fee + self.taker_fee + self.slippage) * nominal_leverage * 0.5
            net_outcome_r = outcome_r - (fee_friction_r if outcome_r != 0 else 0.0)

            trades.append({
                "symbol": symbol,
                "interval": interval,
                "entry_time": str(df.iloc[fill_idx]["timestamp"]),
                "exit_time": str(df.iloc[exit_idx]["timestamp"]),
                "tp1_time": str(df.iloc[tp1_idx]["timestamp"]) if hit_tp1 and tp1_idx is not None else None,
                "bars_held": exit_idx - fill_idx,
                "direction": direction,
                "entry": entry,
                "sl": sl,
                "confluence_score": 75,
                "ker": round(ker_val, 3),
                "adx": round(adx_val, 2),
                "is_elastic": is_elastic,
                "scaled_in": False,
                "risk_pct": round((risk/entry)*100, 2),
                "outcome_r": round(net_outcome_r, 2),
                "close_reason": close_reason or ("EXPIRED_HORIZON" if outcome_r >= 0 else "STOP_LOSS")
            })
            last_trade_exit_idx = exit_idx

        return trades

    def run_adaptive_portfolio_audit(self) -> Dict[str, Any]:
        """
        Ejecuta la auditoría oficial del portafolio con paridad SSoT v31.0.
        """
        btc_map = self._load_btc_macro_map()
        all_results = []

        print("="*85)
        print("👑  AUDITORÍA OFICIAL SLINGSHOT v41.0 APEX ZENITH SOVEREIGN (SOP-36 A SOP-38 SSoT)")
        print("="*85)
        print(f"💰 Capital Base: ${self.initial_balance:,.2f} USD | Riesgo Base: {self.risk_pct*100:.2f}% | Comisiones Bitunix Descontadas")
        print("="*85)

        all_assets = MEGA_CAPS + HIGH_BETA_ALTS
        seen = set()
        for sym in all_assets:
            if sym in seen:
                continue
            seen.add(sym)
            t_list = self.run_single_asset(sym, interval="15m", btc_map=btc_map)
            all_results.extend(t_list)

        df_all = pd.DataFrame(all_results)
        if df_all.empty:
            print("⚠️ No se encontraron operaciones para los criterios seleccionados.")
            return {}

        total_trades = len(df_all)
        winners = df_all[df_all["outcome_r"] > 0]
        losers = df_all[df_all["outcome_r"] < 0]
        breakevens = df_all[df_all["outcome_r"] == 0]

        win_rate = (len(winners) / total_trades) * 100
        be_rate = (len(breakevens) / total_trades) * 100
        total_r = df_all["outcome_r"].sum()
        gross_profit_r = winners["outcome_r"].sum() if len(winners) > 0 else 0.0
        gross_loss_r = abs(losers["outcome_r"].sum()) if len(losers) > 0 else 1.0
        profit_factor = gross_profit_r / gross_loss_r if gross_loss_r > 0 else 99.0
        expectancy_r = total_r / total_trades

        # Drawdown Base Plano
        risk_usd = self.initial_balance * self.risk_pct
        df_all["pnl_usd"] = df_all["outcome_r"] * risk_usd
        df_all["cum_pnl"] = df_all["pnl_usd"].cumsum()
        df_all["equity"] = self.initial_balance + df_all["cum_pnl"]
        df_all["peak"] = df_all["equity"].cummax()
        df_all["dd_pct"] = (df_all["equity"] - df_all["peak"]) / df_all["peak"] * 100
        max_drawdown = abs(df_all["dd_pct"].min())

        # ── SOP-33 & SOP-38: ALPHA-TIER SIZING ASIMÉTRICO & SNIPER NY OPEN ──
        def get_trade_sizing(row):
            sym = row["symbol"]
            et = pd.to_datetime(row["entry_time"])
            h = et.hour
            cs = float(row.get("confluence_score", 75.0))
            return RiskManager.calculate_alpha_tier_sizing(sym, confluence_score=cs, hour_utc=h)

        df_all["sizing_mult"] = df_all.apply(get_trade_sizing, axis=1)
        df_scaled = df_all[df_all["sizing_mult"] > 0].copy().reset_index(drop=True)
        df_scaled["pnl_usd_scaled"] = df_scaled["outcome_r"] * risk_usd * df_scaled["sizing_mult"]
        df_scaled["cum_pnl_scaled"] = df_scaled["pnl_usd_scaled"].cumsum()
        df_scaled["equity_scaled"] = self.initial_balance + df_scaled["cum_pnl_scaled"]
        df_scaled["peak_scaled"] = df_scaled["equity_scaled"].cummax()
        df_scaled["dd_pct_scaled"] = (df_scaled["equity_scaled"] - df_scaled["peak_scaled"]) / df_scaled["peak_scaled"] * 100
        scaled_max_dd = abs(df_scaled["dd_pct_scaled"].min())
        scaled_net_usd = df_scaled["pnl_usd_scaled"].sum()
        scaled_total_r = (df_scaled["outcome_r"] * df_scaled["sizing_mult"]).sum()
        scaled_wins = df_scaled[df_scaled["outcome_r"] > 0]
        scaled_losses = df_scaled[df_scaled["outcome_r"] < 0]
        scaled_pf = (scaled_wins["outcome_r"] * scaled_wins["sizing_mult"]).sum() / abs((scaled_losses["outcome_r"] * scaled_losses["sizing_mult"]).sum())

        print(f"📊 Total Operaciones Auditadas  : {total_trades}")
        print(f"🎯 Win Rate Real (TP0 / TP1 / TP2 / TP3): {win_rate:.1f}% ({len(winners)} Ganadoras / {len(losers)} Pérdidas)")
        print(f"🛡️ Tasa de Cero Ganancia ($0)    : {be_rate:.1f}% ({len(breakevens)} trades en $0 exacto)")
        print(f"⚖️ Profit Factor Base           : {profit_factor:.2f}  |  🚀 Con Alpha-Tier Sizing: {scaled_pf:.2f}")
        print(f"💎 Retorno Total Base en R      : {total_r:>+8.2f} R |  💎 Con Alpha-Tier Sizing: {scaled_total_r:>+8.2f} R")
        print(f"💵 Beneficio Neto USD           : {df_all['pnl_usd'].sum():>+11,.2f} USD |  🚀 Con Alpha-Tier: {scaled_net_usd:>+11,.2f} USD")
        print(f"📉 Drawdown Máximo Portafolio   : -{max_drawdown:.2f}% (Base)  |  🛡️ Con Alpha-Tier: -{scaled_max_dd:.2f}% (Blindaje FTMO)")
        print(f"📈 Esperanza Matemática por Op  : {expectancy_r:>+7.3f} R / trade")
        print("="*85)

        print("\n📋 DESGLOSE POR ACTIVO (ORDENADO POR RETORNO NETO):")
        print("-"*85)
        asset_summary = df_all.groupby("symbol").agg(
            Trades=("outcome_r", "count"),
            Win_Rate=("outcome_r", lambda x: f"{(x > 0).mean()*100:.1f}%"),
            Retorno_R=("outcome_r", lambda x: f"{x.sum():+.2f} R"),
            Profit_Factor=("outcome_r", lambda x: f"{x[x>0].sum()/abs(x[x<0].sum()) if (x<0).sum()!=0 else 99:.2f}")
        )
        asset_ret_num = df_all.groupby("symbol")["outcome_r"].sum()
        asset_summary = asset_summary.loc[asset_ret_num.sort_values(ascending=False).index]
        print(asset_summary.to_string())
        print("="*85)

        # Exportar reporte inmutable
        reports_dir = os.path.join(os.path.dirname(__file__), "reports")
        os.makedirs(reports_dir, exist_ok=True)
        report_path = os.path.join(reports_dir, "unified_institutional_backtest_report.json")

        summary_payload = {
            "audit_date": datetime.now().isoformat(),
            "engine_version": "v31.0 APEX TITAN (Dynamic Gating SSoT)",
            "total_trades": total_trades,
            "win_rate": round(win_rate, 2),
            "breakeven_rate": round(be_rate, 2),
            "total_r": round(total_r, 2),
            "profit_factor": round(profit_factor, 2),
            "expectancy_r": round(expectancy_r, 4),
            "max_drawdown_pct": round(max_drawdown, 2),
            "trades": all_results
        }
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(summary_payload, f, indent=4)

        print(f"💾 Reporte Oficial Inmutable guardado en: {report_path}\n")
        return summary_payload

    def run_chronological_portfolio_replay(
        self,
        max_concurrent_longs: int = 2,
        max_heat_pct: float = 7.5,
        strict_btc_macro: bool = True,
        toxic_hours: Optional[List[int]] = None,
        excluded_assets: Optional[List[str]] = None,
        enable_compounding: bool = True,
        dynamic_risk_pct: float = 0.025,
        compounding_initial_usd: float = 1_000.0,
        enable_alpha_cycle: bool = False,
        enable_trinity_boost: bool = False,
        enable_elastic_runner: bool = False,
        enable_golden_hours: bool = False,
        enable_regime_agent: bool = False,
    ) -> Dict[str, Any]:
        """
        [EVENT-DRIVEN TIMELINE REPLAY v50.0]
        Simulador Cronológico Unificado de Cartera con Réplica 1-a-1 de Producción:
        - Reloj Global Unificado cruzando todos los activos en el tiempo.
        - Filtro Macro BTC dinámico en tiempo real (btc_aligned).
        - Concurrencia de cartera y reciclaje dinámico de slots (SOP-30 & SOP-44).
        - Modo Dual: R Base / Alpha-Tier (1% plano) e Interés Compuesto Dinámico (2.5% Bitunix).
        - Embudo de telemetría de señales.
        - Modulación Táctica de Régimen de Mercado SOP-63 (SlingshotRegimeAgent).
        """
        toxic_hours = [10, 14] if toxic_hours is None else toxic_hours
        excluded_assets = ["RENDERUSDT"] if excluded_assets is None else excluded_assets

        btc_map = self._load_btc_macro_map()
        all_assets = MEGA_CAPS + HIGH_BETA_ALTS
        all_results = []
        seen = set()

        print("=" * 88)
        print("🏛️  SIMULADOR CRONOLÓGICO UNIFICADO DE CARTERA (EVENT-DRIVEN SSoT v50.0)")
        print("=" * 88)
        print(f"⚙️  Concurrencia Máxima Longs : {max_concurrent_longs} posiciones simultáneas (SOP-30)")
        print(f"🛡️  Calor Máximo de Cartera   : {max_heat_pct}% (SOP-44 Directional Heat Guardrail)")
        print(f"🧭  Filtro Macro BTC         : {'ACTIVO (btc_aligned dinámico)' if strict_btc_macro else 'DESACTIVADO'}")
        print(f"⏳  Quirófano Horario        : Vetadas horas {toxic_hours} UTC (Trampa Londres & Apertura NY)")
        print(f"✂️  Poda de Activos Tóxicos  : Excluidos {excluded_assets}")
        print(f"🔄  Reciclaje de Slots       : ACTIVO (Liberación de riesgo al tocar TP1 @ Breakeven)")
        adv_active = enable_alpha_cycle or enable_trinity_boost or enable_elastic_runner or enable_golden_hours or enable_regime_agent
        if adv_active:
            print(f"🌟  Protocolos Alpha Avanzados: SOP-46 Cycle: {enable_alpha_cycle} | SOP-47 Trinity: {enable_trinity_boost} | SOP-48 KER: {enable_elastic_runner} | SOP-49 Hours: {enable_golden_hours} | SOP-63 Regime: {enable_regime_agent}")
        print("=" * 88)

        # 1. Extracción de setups brutos
        for sym in all_assets:
            if sym in seen:
                continue
            seen.add(sym)
            t_list = self.run_single_asset(
                sym,
                interval="15m",
                btc_map=btc_map,
                enable_elastic_runner=enable_elastic_runner
            )
            all_results.extend(t_list)

        df_all = pd.DataFrame(all_results)
        if df_all.empty:
            print("⚠️ No se encontraron operaciones para los criterios seleccionados.")
            return {}

        df_all = df_all.sort_values("entry_time").reset_index(drop=True)
        raw_signal_count = len(df_all)

        # 2. Replay Cronológico con Máquina de Estados
        active_risk_positions = []
        executed_trades = []
        rejected_macro_btc = 0
        rejected_max_slots = 0
        rejected_portfolio_heat = 0
        rejected_toxic_hours = 0

        for idx, tr in df_all.iterrows():
            entry_dt = pd.to_datetime(tr["entry_time"])
            exit_dt = pd.to_datetime(tr["exit_time"])
            tp1_time = tr.get("tp1_time")
            risk_freed_dt = pd.to_datetime(tp1_time) if tp1_time and str(tp1_time) != "None" else exit_dt

            sym = tr["symbol"]
            direction = tr["direction"]
            h = entry_dt.hour

            # Poda de activos
            if excluded_assets and sym in excluded_assets:
                continue

            # Quirófano Horario
            if toxic_hours and h in toxic_hours:
                rejected_toxic_hours += 1
                continue

            # Veto Macro BTC en Vivo (btc_aligned)
            if strict_btc_macro and sym != "BTCUSDT":
                btc_trend = btc_map.get(entry_dt, "NEUTRAL")
                aligned = (direction == "LONG" and btc_trend == "BULLISH") or (direction == "SHORT" and btc_trend == "BEARISH")
                if not aligned:
                    rejected_macro_btc += 1
                    continue

            # Limpiar posiciones que ya liberaron su riesgo antes de este timestamp
            active_risk_positions = [p for p in active_risk_positions if p["risk_freed_time"] > entry_dt]

            # Verificación de Concurrencia de Cartera (SOP-30)
            same_dir_active = [p for p in active_risk_positions if p["direction"] == direction]
            if direction == "LONG" and len(same_dir_active) >= max_concurrent_longs:
                rejected_max_slots += 1
                continue

            # Verificación de Calor de Cartera (SOP-44)
            current_heat = len(active_risk_positions) * (self.risk_pct * 100)
            if current_heat + (self.risk_pct * 100) > max_heat_pct:
                rejected_portfolio_heat += 1
                continue

            # Registrar posición activa en riesgo (libera slot al tocar TP1 @ Breakeven)
            active_risk_positions.append({
                "symbol": sym,
                "direction": direction,
                "entry_time": entry_dt,
                "risk_freed_time": risk_freed_dt,
                "exit_time": exit_dt
            })
            executed_trades.append(tr)

        df_exec = pd.DataFrame(executed_trades).reset_index(drop=True)
        executed_count = len(df_exec)

        if df_exec.empty:
            print("⚠️ Ninguna operación superó los filtros de concurrencia y macro.")
            return {}

        # 3. Métricas Modo 1: Institucional R Base & Alpha-Tier (Riesgo 1.0% Plano)
        def get_trade_sizing(row):
            s = row["symbol"]
            et = pd.to_datetime(row["entry_time"])
            h = et.hour
            dow = et.day_name()
            cs = float(row.get("confluence_score", 75.0))
            
            # SOP-63: Inferencia de Régimen Táctico
            reg_mult = 1.0
            if enable_regime_agent:
                tr_adx = float(row.get("adx", 22.0))
                tr_ker = float(row.get("ker", 0.35))
                btc_tr = btc_map.get(et, "NEUTRAL") if btc_map else "NEUTRAL"
                
                # Reglas del Agente de Régimen SOP-63
                if tr_adx < 18.5 and tr_ker < 0.28:
                    reg_mult = 0.65  # Chop compression (defensivo)
                elif btc_tr == "BULLISH" and tr_ker >= 0.40 and tr_adx >= 20.0:
                    reg_mult = 1.30  # Bull expansion
                elif btc_tr == "BEARISH" and tr_ker >= 0.40 and tr_adx >= 20.0:
                    reg_mult = 1.15  # Bear expansion
                elif tr_adx >= 45.0 and tr_ker < 0.30:
                    reg_mult = 0.50  # High vol shock
                else:
                    reg_mult = 1.00

            return RiskManager.calculate_alpha_tier_sizing(
                s,
                confluence_score=cs,
                hour_utc=h,
                day_of_week=dow,
                apply_alpha_cycle=enable_alpha_cycle,
                apply_trinity_boost=enable_trinity_boost,
                apply_golden_hours=enable_golden_hours,
                regime_mult=reg_mult
            )

        df_exec["sizing_mult"] = df_exec.apply(get_trade_sizing, axis=1)

        winners = df_exec[df_exec["outcome_r"] > 0]
        losers = df_exec[df_exec["outcome_r"] < 0]
        breakevens = df_exec[df_exec["outcome_r"] == 0]

        win_rate = (len(winners) / executed_count) * 100
        be_rate = (len(breakevens) / executed_count) * 100
        total_r_base = df_exec["outcome_r"].sum()
        total_r_alpha = (df_exec["outcome_r"] * df_exec["sizing_mult"]).sum()

        gp_base = winners["outcome_r"].sum() if len(winners) > 0 else 0.0
        gl_base = abs(losers["outcome_r"].sum()) if len(losers) > 0 else 1.0
        pf_base = gp_base / gl_base if gl_base > 0 else 99.0

        gp_alpha = (winners["outcome_r"] * winners["sizing_mult"]).sum() if len(winners) > 0 else 0.0
        gl_alpha = abs((losers["outcome_r"] * losers["sizing_mult"]).sum()) if len(losers) > 0 else 1.0
        pf_alpha = gp_alpha / gl_alpha if gl_alpha > 0 else 99.0

        # Drawdowns Modo 1 ($100k capital base)
        risk_usd_base = self.initial_balance * self.risk_pct
        df_exec["cum_pnl_base"] = (df_exec["outcome_r"] * risk_usd_base).cumsum()
        df_exec["equity_base"] = self.initial_balance + df_exec["cum_pnl_base"]
        df_exec["peak_base"] = df_exec["equity_base"].cummax()
        max_dd_base = abs(((df_exec["equity_base"] - df_exec["peak_base"]) / df_exec["peak_base"] * 100).min())

        df_exec["cum_pnl_alpha"] = (df_exec["outcome_r"] * risk_usd_base * df_exec["sizing_mult"]).cumsum()
        df_exec["equity_alpha"] = self.initial_balance + df_exec["cum_pnl_alpha"]
        df_exec["peak_alpha"] = df_exec["equity_alpha"].cummax()
        max_dd_alpha = abs(((df_exec["equity_alpha"] - df_exec["peak_alpha"]) / df_exec["peak_alpha"] * 100).min())

        # 4. Métricas Modo 2: Crecimiento Cripto Bitunix (Interés Compuesto Automático SOP-39)
        cap = compounding_initial_usd
        peak_cap = compounding_initial_usd
        max_comp_dd = 0.0
        comp_equity_curve = [cap]

        for _, r in df_exec.iterrows():
            trade_risk = cap * dynamic_risk_pct
            trade_pnl = r["outcome_r"] * trade_risk * r["sizing_mult"]
            cap += trade_pnl
            comp_equity_curve.append(cap)
            if cap > peak_cap:
                peak_cap = cap
            dd = (peak_cap - cap) / peak_cap * 100.0
            if dd > max_comp_dd:
                max_comp_dd = dd

        comp_roi_pct = ((cap - compounding_initial_usd) / compounding_initial_usd) * 100.0

        # 5. Impresión de Resultados Institucionales
        print("\n📊 1. EMBUDO DE SELECCIÓN Y FILTRADO INSTITUCIONAL:")
        print("-" * 88)
        print(f" • Señales Estructurales Brutas Detectadas : {raw_signal_count}")
        print(f" • Vetadas por Filtro Macro BTC (btc_aligned): {rejected_macro_btc:>4} ({rejected_macro_btc/raw_signal_count*100:.1f}%)")
        print(f" • Vetadas por Horas Tóxicas (10h/14h UTC)  : {rejected_toxic_hours:>4} ({rejected_toxic_hours/raw_signal_count*100:.1f}%)")
        print(f" • Vetadas por Límite de Slots (SOP-30)     : {rejected_max_slots:>4} ({rejected_max_slots/raw_signal_count*100:.1f}%)")
        print(f" • Vetadas por Calor de Cartera (SOP-44)   : {rejected_portfolio_heat:>4} ({rejected_portfolio_heat/raw_signal_count*100:.1f}%)")
        print(f" • Operaciones Reales Ejecutadas            : {executed_count:>4} ({executed_count/raw_signal_count*100:.1f}%)")
        print("=" * 88)

        print("💎 2. RENDIMIENTO MODO AUDITORÍA (RIESGO PLANO 1.00% / PROP FIRM SSoT):")
        print("-" * 88)
        print(f" • Total Operaciones Auditadas  : {executed_count}")
        print(f" • Win Rate Real (TP1 / TP2 / TP3): {win_rate:.1f}% ({len(winners)} Ganadoras / {len(losers)} Pérdidas)")
        print(f" • Tasa de Cero Ganancia ($0)    : {be_rate:.1f}% ({len(breakevens)} Breakevens)")
        print(f" • Profit Factor Base           : {pf_base:.2f}  |  🚀 Con Alpha-Tier Sizing: {pf_alpha:.2f}")
        print(f" • Retorno Total Base en R      : {total_r_base:>+8.2f} R |  💎 Con Alpha-Tier Sizing: {total_r_alpha:>+8.2f} R")
        print(f" • Drawdown Máximo Portafolio   : -{max_dd_base:.2f}% (Base)  |  🛡️ Con Alpha-Tier: -{max_dd_alpha:.2f}% (Blindaje FTMO)")
        print(f" • Esperanza Matemática por Op  : {total_r_base/executed_count:>+7.3f} R / trade")
        print("=" * 88)

        print(f"🚀 3. RENDIMIENTO MODO CRECIMIENTO BITUNIX (INTERÉS COMPUESTO 2.50% SOP-39):")
        print("-" * 88)
        print(f" • Capital Inicial Simulado     : ${compounding_initial_usd:,.2f} USD")
        print(f" • Capital Final Acumulado      : ${cap:,.2f} USD")
        print(f" • Retorno Neto Compuesto (ROI) : +{comp_roi_pct:,.1f}% (x{cap/compounding_initial_usd:.1f} de multiplicación)")
        print(f" • Drawdown Máximo Compuesto    : -{max_comp_dd:.2f}%")
        print("=" * 88)

        # Métricas formales SOP-60 (Sharpe, Sortino, Expectancy, Max DD R)
        from engine.core.tear_sheet import calculate_portfolio_metrics
        alpha_returns = (df_exec["outcome_r"] * df_exec["sizing_mult"]).tolist()
        sop60_metrics = calculate_portfolio_metrics(alpha_returns)

        print("📈 4. MÉTRICAS FINANCIERAS FORMALES DE CARTERA (SOP-60 TEAR SHEET):")
        print("-" * 88)
        print(f" • Sharpe Ratio Anualizado      : {sop60_metrics['sharpe_ratio']:.2f}")
        print(f" • Sortino Ratio (Downside Risk): {sop60_metrics['sortino_ratio']:.2f}")
        print(f" • Esperanza Matemática (E)     : {sop60_metrics['expectancy_r']:>+7.3f} R / trade")
        print(f" • Ganancia Media vs Pérdida    : +{sop60_metrics['avg_win_r']:.2f}R / {sop60_metrics['avg_loss_r']:.2f}R")
        print(f" • Max Drawdown en R            : -{sop60_metrics['max_drawdown_r']:.2f} R")
        print("=" * 88)

        # Exportar reporte inmutable
        reports_dir = os.path.join(os.path.dirname(__file__), "reports")
        os.makedirs(reports_dir, exist_ok=True)
        report_path = os.path.join(reports_dir, "chronological_backtest_report.json")

        summary_payload = {
            "audit_date": datetime.now().isoformat(),
            "engine_version": "v50.0 APEX EXPANSION (Event-Driven Timeline SSoT)",
            "advanced_protocols": {
                "alpha_cycle_sop46": enable_alpha_cycle,
                "trinity_boost_sop47": enable_trinity_boost,
                "elastic_runner_sop48": enable_elastic_runner,
                "golden_hours_sop49": enable_golden_hours,
                "regime_agent_sop63": enable_regime_agent
            },
            "telemetry_funnel": {
                "raw_signals": raw_signal_count,
                "rejected_macro_btc": rejected_macro_btc,
                "rejected_max_slots": rejected_max_slots,
                "rejected_portfolio_heat": rejected_portfolio_heat,
                "executed_trades": executed_count
            },
            "institutional_mode": {
                "total_trades": executed_count,
                "win_rate": round(win_rate, 2),
                "breakeven_rate": round(be_rate, 2),
                "total_r_base": round(total_r_base, 2),
                "total_r_alpha": round(total_r_alpha, 2),
                "profit_factor_base": round(pf_base, 2),
                "profit_factor_alpha": round(pf_alpha, 2),
                "max_drawdown_base_pct": round(max_dd_base, 2),
                "max_drawdown_alpha_pct": round(max_dd_alpha, 2),
                "sharpe_ratio": sop60_metrics["sharpe_ratio"],
                "sortino_ratio": sop60_metrics["sortino_ratio"],
                "expectancy_r": sop60_metrics["expectancy_r"],
                "max_drawdown_r": sop60_metrics["max_drawdown_r"]
            },
            "compounding_mode": {
                "initial_usd": compounding_initial_usd,
                "final_usd": round(cap, 2),
                "roi_pct": round(comp_roi_pct, 2),
                "max_drawdown_pct": round(max_comp_dd, 2)
            },
            "trades": df_exec.to_dict(orient="records")
        }
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(summary_payload, f, indent=4, default=str)

        print(f"💾 Reporte Cronológico Inmutable guardado en: {report_path}\n")
        return summary_payload


if __name__ == "__main__":
    engine = UnifiedBacktestEngine()
    engine.run_chronological_portfolio_replay()

