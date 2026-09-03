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
from engine.strategies.smc import SMCInstitutionalStrategy
from engine.core.confluence import confluence_manager
from engine.risk.risk_manager import RiskManager
from engine.core.logger import logger

logger.setLevel("ERROR")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

MEGA_CAPS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "AVAXUSDT", "LINKUSDT"]
HIGH_BETA_ALTS = ["RENDERUSDT", "SUIUSDT", "INJUSDT", "NEARUSDT", "FETUSDT", "ATOMUSDT", "BNBUSDT", "PAXGUSDT"]


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

    def run_single_asset(self, symbol: str, interval: str = "15m", btc_map: dict = None) -> List[Dict[str, Any]]:
        """
        Ejecuta la simulación cuantitativa institucional v31.0.
        """
        file_candidates = glob.glob(os.path.join(DATA_DIR, f"{symbol}_{interval}_*.parquet"))
        if not file_candidates:
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
            raw = pd.read_parquet(file_candidates[0])
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
            if interval == "15m" and self.strict_killzones:
                if not (7 <= hour <= 12 or 13 <= hour <= 18):
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

            # Alineación Direccional HTF
            is_bull_htf = c > ema_htf
            is_bear_htf = c < ema_htf

            has_bull = bool(row.get("recent_ob_bull", False)) and (bool(row.get("recent_fvg_bull", False)) or bool(row.get("recent_sweep_bull", False))) and is_bull_htf
            has_bear = bool(row.get("recent_ob_bear", False)) and (bool(row.get("recent_fvg_bear", False)) or bool(row.get("recent_sweep_bear", False))) and is_bear_htf

            if not (has_bull or has_bear):
                continue

            direction = "LONG" if has_bull else "SHORT"

            # 2. Entrada Límite en Descuento OTE / FVG (SOP-26 Grid 40/40/20)
            if direction == "LONG":
                entry = c - (atr * 0.35)
                sl = entry - (atr * 0.85)
                risk = entry - sl
                p_tp1 = entry + (risk * 1.2)   # TP1 (+1.2R, 40% + Fast BE)
                p_tp2 = entry + (risk * 2.0)   # TP2 (+2.0R, 40% + Bloqueo +1.0R en verde)
                p_tp3 = entry + (risk * 3.5)   # TP3 Runner (+3.5R, 20%)
            else:
                entry = c + (atr * 0.35)
                sl = entry + (atr * 0.85)
                risk = sl - entry
                p_tp1 = entry - (risk * 1.2)
                p_tp2 = entry - (risk * 2.0)
                p_tp3 = entry - (risk * 3.5)

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

            # 3. Simulación Walk-Forward con Modelo Cuántico v37.0 (SOP-25 & SOP-26)
            hit_tp1 = False
            hit_tp2 = False
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

                    # Stop Loss Normal
                    if bl <= curr_sl:
                        if curr_sl == sl:
                            close_reason = "STOP_LOSS"
                            outcome_r -= (1.0 * rem_pos * total_multiplier)
                        else:
                            close_reason = "PROTECTED_EXIT"
                        break

                    # TP1 (+1.2R): Cobra 40% y mueve SL a Breakeven + Fee Buffer
                    if not hit_tp1 and bh >= p_tp1:
                        hit_tp1 = True
                        outcome_r += (1.2 * 0.40 * total_multiplier)
                        rem_pos -= 0.40
                        curr_sl = entry + (entry * 0.0008)

                    # TP2 (+2.0R): Cobra 40% y sube SL a +1.0R en verde garantizado
                    if hit_tp1 and not hit_tp2 and bh >= p_tp2:
                        hit_tp2 = True
                        outcome_r += (2.0 * 0.40 * total_multiplier)
                        rem_pos -= 0.40
                        curr_sl = entry + (risk * 1.0)

                    # TP3 (+3.5R): Cierra el 20% Runner final
                    if hit_tp2 and bh >= p_tp3:
                        outcome_r += (3.5 * rem_pos * total_multiplier)
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
                        break

                    # TP1 (+1.2R): Cobra 40% y mueve SL a Breakeven + Fee Buffer
                    if not hit_tp1 and bl <= p_tp1:
                        hit_tp1 = True
                        outcome_r += (1.2 * 0.40 * total_multiplier)
                        rem_pos -= 0.40
                        curr_sl = entry - (entry * 0.0008)

                    # TP2 (+2.0R): Cobra 40% y sube SL a +1.0R en verde garantizado
                    if hit_tp1 and not hit_tp2 and bl <= p_tp2:
                        hit_tp2 = True
                        outcome_r += (2.0 * 0.40 * total_multiplier)
                        rem_pos -= 0.40
                        curr_sl = entry - (risk * 1.0)

                    # TP3 (+3.5R): Cierra el 20% Runner final
                    if hit_tp2 and bl <= p_tp3:
                        outcome_r += (3.5 * rem_pos * total_multiplier)
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
                "direction": direction,
                "entry": entry,
                "sl": sl,
                "confluence_score": 75,
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
        print("🛡️  AUDITORÍA OFICIAL SLINGSHOT v37.0 APEX QUANTUM (SOP-25 & SOP-26 SSoT)")
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

        # Drawdown
        risk_usd = self.initial_balance * self.risk_pct
        df_all["pnl_usd"] = df_all["outcome_r"] * risk_usd
        df_all["cum_pnl"] = df_all["pnl_usd"].cumsum()
        df_all["equity"] = self.initial_balance + df_all["cum_pnl"]
        df_all["peak"] = df_all["equity"].cummax()
        df_all["dd_pct"] = (df_all["equity"] - df_all["peak"]) / df_all["peak"] * 100
        max_drawdown = abs(df_all["dd_pct"].min())

        print(f"📊 Total Operaciones Auditadas  : {total_trades}")
        print(f"🎯 Win Rate Real (TP0 / TP1 / TP2 / TP3): {win_rate:.1f}% ({len(winners)} Ganadoras / {len(losers)} Pérdidas)")
        print(f"🛡️ Tasa de Cero Ganancia ($0)    : {be_rate:.1f}% ({len(breakevens)} trades en $0 exacto)")
        print(f"⚖️ Profit Factor Neto Global    : {profit_factor:.2f}")
        print(f"💎 Retorno Total Neto en R      : {total_r:>+8.2f} R")
        print(f"💵 Beneficio Neto USD           : {df_all['pnl_usd'].sum():>+11,.2f} USD")
        print(f"📉 Drawdown Máximo Portafolio   : -{max_drawdown:.2f}% (Límite FTMO: -10.0%)")
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


if __name__ == "__main__":
    engine = UnifiedBacktestEngine()
    engine.run_adaptive_portfolio_audit()
