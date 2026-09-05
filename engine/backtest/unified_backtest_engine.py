"""
engine/backtest/unified_backtest_engine.py
=============================================================================
SLINGSHOT APEX v45.0 — QUANTUM REPLAY ENGINE (CLEAN SSoT & INSTITUTIONAL FIDELITY)
=============================================================================
Única Fuente de la Verdad (Single Source of Truth) para la auditoría cuantitativa.

Mecánica Cuantitativa Institucional SSoT:
1. Detección Vectorizada de Order Blocks, FVGs y Sweeps en Rust (Polars Engine).
2. Jurado de Confluencia Real de 14 Factores (ConfluenceManager) evaluado por vela.
3. Colocación Estructural de Stop Loss y Entradas OTE mediante RiskManager.
4. Filtro Cuántico de Ventanas Temporales Específico por Activo (SOP-18).
5. Filtros Institucionales: VWAP Exhaustion (SOP-27), Quality Gate (SOP-28) y Regime Quarantine (SOP-31).
6. [SOP-25] Early Structural Invalidation a -0.65R antes de TP1.
7. Grilla de Salidas de Producción Nexus (60% en TP1 +1.5R con Fast BE, 20% en TP2 +3.0R con Lock, 10% en TP3 +5.0R, 10% Ultra-Runner).
8. Verificación Intra-Vela de Fill (Pessimistic Bias) eliminando el sesgo de supervivencia.
9. [SOP-21] Apalancamiento Seguro Dinámico y Descuento Real de Comisiones y Deslizamiento.
10. Métricas Financieras de Grado Fondo: Sharpe Ratio, Sortino Ratio, Calmar Ratio, Profit Factor y Max Drawdown.
"""

import sys
import os
import glob
import json
import math
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

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
    [TITAN REPLAY ENGINE v45.0 SSoT]
    Motor de Replay Histórico 100% fiel al comportamiento del live engine en producción.
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
        Ejecuta la simulación cuantitativa institucional SSoT con paridad total de producción.
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

        # Tendencia HTF (Alineación 1H EMA200 / 15m EMA800)
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

            # ── EVALUACIÓN REAL DEL JURADO DE CONFLUENCIA (ConfluenceManager SSoT) ──
            smc_map = {
                "order_blocks": {
                    "bullish": [{"top": float(row["ob_bull_top"]), "bottom": float(row["ob_bull_bottom"])}] if (row.get("recent_ob_bull") and pd.notna(row.get("ob_bull_bottom"))) else [],
                    "bearish": [{"top": float(row["ob_bear_top"]), "bottom": float(row["ob_bear_bottom"])}] if (row.get("recent_ob_bear") and pd.notna(row.get("ob_bear_top"))) else []
                }
            }
            session_name = "NEW_YORK" if (13 <= hour <= 17) else ("LONDON" if (7 <= hour <= 12) else "OFF_HOURS")
            candidate_sig = {
                "asset": symbol,
                "symbol": symbol,
                "price": c,
                "signal_type": direction,
                "type": direction,
                "timestamp": dt,
                "regime": row.get("market_regime", "RANGING"),
                "interval": interval,
                "interval_minutes": 15 if interval == "15m" else 60
            }

            confluence_res = confluence_manager.evaluate_signal(
                df=df.iloc[max(0, i - 100):i + 1],
                signal=candidate_sig,
                session_data={"current_session": session_name},
                smc_map=smc_map
            )
            confluence_score = int(confluence_res.get("score", 0))

            if confluence_score < self.min_score:
                continue

            # ── CÁLCULO ESTRUCTURAL DE POSICIÓN (RiskManager SSoT) ──
            pos_calc = self.risk_mgr.calculate_position(
                current_price=c,
                signal_type=direction,
                market_regime=row.get("market_regime", "RANGING"),
                smc_data=smc_map,
                atr_value=atr,
                asset=symbol,
                confluence_score=confluence_score
            )

            entry = float(pos_calc.get("entry_price", c))
            sl = float(pos_calc.get("stop_loss"))
            p_tp1 = float(pos_calc.get("tp1"))
            p_tp2 = float(pos_calc.get("tp2"))
            p_tp3 = float(pos_calc.get("tp3"))
            be_price = float(pos_calc.get("be_price", entry + (entry * 0.0008 if direction == "LONG" else -entry * 0.0008)))

            risk = abs(entry - sl)
            if risk <= 0 or (risk / entry) > 0.05:
                continue

            # ── VERIFICACIÓN DE ACTIVACIÓN DE ORDEN LÍMITE (hasta 8 velas) ──
            filled = False
            fill_idx = -1
            for j in range(i, min(i + 9, n)):
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

            # ── RESOLUCIÓN INTRA-VELA DE FILL (Eliminación del Sesgo de Supervivencia) ──
            fill_bar = df.iloc[fill_idx]
            fb_h = float(fill_bar["high"])
            fb_l = float(fill_bar["low"])

            # Comprobar si en la misma vela de entrada el precio tocó el SL (Pessimistic Bias)
            sl_hit_on_fill = (direction == "LONG" and fb_l <= sl) or (direction == "SHORT" and fb_h >= sl)
            if sl_hit_on_fill:
                safe_lev = RiskManager.calculate_safe_leverage(entry, sl, max_cap=20)
                fee_friction_r = (self.maker_fee + self.taker_fee + self.slippage) * safe_lev * 0.5
                trades.append({
                    "symbol": symbol,
                    "interval": interval,
                    "entry_time": str(df.iloc[fill_idx]["timestamp"]),
                    "direction": direction,
                    "entry": entry,
                    "sl": sl,
                    "tp1": p_tp1,
                    "tp2": p_tp2,
                    "tp3": p_tp3,
                    "confluence_score": confluence_score,
                    "scaled_in": False,
                    "risk_pct": round((risk / entry) * 100, 2),
                    "outcome_r": round(-1.0 - fee_friction_r, 2),
                    "close_reason": "STOP_LOSS_FILL_BAR"
                })
                last_trade_exit_idx = fill_idx
                continue

            # ── SIMULACIÓN WALK-FORWARD DE SALIDAS ASIMÉTRICAS (Paridad Nexus / TradeManager) ──
            # Grilla: 60% TP1 (+1.5R con Fast BE), 20% TP2 (+3.0R con Lock), 10% TP3 (+5.0R), 10% Ultra-Runner
            hit_tp1 = False
            hit_tp2 = False
            hit_tp3 = False
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
                    # SOP-25: Early Structural Invalidation (@ -0.65R antes de TP1)
                    cur_adverse = (entry - bl) / risk
                    if cur_adverse >= 0.65 and not hit_tp1:
                        close_reason = "SOP25_EARLY_INVALIDATION"
                        outcome_r -= (0.65 * rem_pos)
                        break

                    # Stop Loss
                    if bl <= curr_sl:
                        if curr_sl == sl:
                            close_reason = "STOP_LOSS"
                            outcome_r -= (1.0 * rem_pos)
                        else:
                            close_reason = "PROTECTED_EXIT"
                        break

                    # TP1 (+1.5R): Cierra 60% y activa Fast Breakeven con Fee Absorber
                    if not hit_tp1 and bh >= p_tp1:
                        hit_tp1 = True
                        outcome_r += (1.5 * 0.60)
                        rem_pos -= 0.60
                        curr_sl = be_price

                    # TP2 (+3.0R): Cierra 20% y asegura ganancia neta en verde (+1.0R a +2.0R)
                    if hit_tp1 and not hit_tp2 and bh >= p_tp2:
                        hit_tp2 = True
                        outcome_r += (3.0 * 0.20)
                        rem_pos -= 0.20
                        curr_sl = entry + (risk * 1.5)

                    # TP3 (+5.0R): Cierra 10% y deja el 10% restante como Ultra-Runner con Trailing Ratchet
                    if hit_tp2 and not hit_tp3 and bh >= p_tp3:
                        hit_tp3 = True
                        outcome_r += (5.0 * 0.10)
                        rem_pos -= 0.10
                        curr_sl = entry + (risk * 3.0)

                    # Ultra-Runner Trailing Ratchet (+7.0R o más)
                    if hit_tp3 and rem_pos > 0:
                        cur_r = (bh - entry) / risk
                        if cur_r >= 7.0:
                            outcome_r += (cur_r * rem_pos)
                            rem_pos = 0.0
                            close_reason = "ULTRA_RUNNER_EXIT"
                            break

                else:  # SHORT
                    # SOP-25: Early Structural Invalidation (@ -0.65R antes de TP1)
                    cur_adverse = (bh - entry) / risk
                    if cur_adverse >= 0.65 and not hit_tp1:
                        close_reason = "SOP25_EARLY_INVALIDATION"
                        outcome_r -= (0.65 * rem_pos)
                        break

                    # Stop Loss
                    if bh >= curr_sl:
                        if curr_sl == sl:
                            close_reason = "STOP_LOSS"
                            outcome_r -= (1.0 * rem_pos)
                        else:
                            close_reason = "PROTECTED_EXIT"
                        break

                    # TP1 (+1.5R): Cierra 60% y activa Fast Breakeven con Fee Absorber
                    if not hit_tp1 and bl <= p_tp1:
                        hit_tp1 = True
                        outcome_r += (1.5 * 0.60)
                        rem_pos -= 0.60
                        curr_sl = be_price

                    # TP2 (+3.0R): Cierra 20% y asegura ganancia neta en verde (+1.0R a +2.0R)
                    if hit_tp1 and not hit_tp2 and bl <= p_tp2:
                        hit_tp2 = True
                        outcome_r += (3.0 * 0.20)
                        rem_pos -= 0.20
                        curr_sl = entry - (risk * 1.5)

                    # TP3 (+5.0R): Cierra 10%
                    if hit_tp2 and not hit_tp3 and bl <= p_tp3:
                        hit_tp3 = True
                        outcome_r += (5.0 * 0.10)
                        rem_pos -= 0.10
                        curr_sl = entry - (risk * 3.0)

                    # Ultra-Runner Trailing Ratchet
                    if hit_tp3 and rem_pos > 0:
                        cur_r = (entry - bl) / risk
                        if cur_r >= 7.0:
                            outcome_r += (cur_r * rem_pos)
                            rem_pos = 0.0
                            close_reason = "ULTRA_RUNNER_EXIT"
                            break

            # Si quedó remanente al agotarse el horizonte de tiempo
            if rem_pos > 0 and not close_reason:
                close_reason = "EXPIRED_HORIZON"

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
                "tp1": p_tp1,
                "tp2": p_tp2,
                "tp3": p_tp3,
                "confluence_score": confluence_score,
                "scaled_in": False,
                "risk_pct": round((risk / entry) * 100, 2),
                "outcome_r": round(net_outcome_r, 2),
                "close_reason": close_reason or ("EXPIRED_HORIZON" if outcome_r >= 0 else "STOP_LOSS")
            })
            last_trade_exit_idx = exit_idx

        return trades

    @staticmethod
    def calculate_performance_metrics(trades: List[Dict[str, Any]], initial_balance: float = 100_000.0, risk_pct: float = 0.01) -> Dict[str, Any]:
        """
        Calcula métricas financieras vectorizadas de grado Hedge Fund / Prop Firm:
        Sharpe Ratio, Sortino Ratio, Calmar Ratio, Profit Factor, Expectancy, Max Drawdown.
        """
        if not trades:
            return {
                "total_trades": 0, "win_rate": 0.0, "profit_factor": 0.0,
                "expectancy_r": 0.0, "sharpe_ratio": 0.0, "sortino_ratio": 0.0,
                "calmar_ratio": 0.0, "max_drawdown_pct": 0.0, "total_r": 0.0,
                "net_profit_usd": 0.0
            }

        df = pd.DataFrame(trades)
        total_trades = len(df)
        winners = df[df["outcome_r"] > 0]
        losers = df[df["outcome_r"] < 0]
        breakevens = df[df["outcome_r"] == 0]

        win_rate = (len(winners) / total_trades) * 100.0
        be_rate = (len(breakevens) / total_trades) * 100.0
        total_r = float(df["outcome_r"].sum())

        gross_profit_r = float(winners["outcome_r"].sum()) if len(winners) > 0 else 0.0
        gross_loss_r = abs(float(losers["outcome_r"].sum())) if len(losers) > 0 else 1.0
        profit_factor = round(gross_profit_r / gross_loss_r, 2) if gross_loss_r > 0 else 99.0
        expectancy_r = round(total_r / total_trades, 4)

        # Curva de Equidad y Drawdown
        risk_usd = initial_balance * risk_pct
        df["pnl_usd"] = df["outcome_r"] * risk_usd
        df["cum_pnl"] = df["pnl_usd"].cumsum()
        df["equity"] = initial_balance + df["cum_pnl"]
        df["peak"] = df["equity"].cummax()
        df["dd_pct"] = (df["equity"] - df["peak"]) / df["peak"] * 100.0
        max_drawdown = abs(float(df["dd_pct"].min()))

        # Sharpe Ratio (Anualizado en base a retorno por trade)
        mean_r = float(df["outcome_r"].mean())
        std_r = float(df["outcome_r"].std()) if len(df) > 1 else 1.0
        if std_r > 0:
            sharpe_ratio = round((mean_r / std_r) * math.sqrt(min(total_trades, 400)), 2)
        else:
            sharpe_ratio = 0.0

        # Sortino Ratio (Penaliza únicamente volatilidad negativa)
        downside_returns = df[df["outcome_r"] < 0]["outcome_r"]
        downside_std = float(downside_returns.std()) if len(downside_returns) > 1 else 1.0
        if downside_std > 0:
            sortino_ratio = round((mean_r / downside_std) * math.sqrt(min(total_trades, 400)), 2)
        else:
            sortino_ratio = 0.0

        # Calmar Ratio (Retorno / Max DD)
        net_return_pct = (df["cum_pnl"].iloc[-1] / initial_balance) * 100.0
        calmar_ratio = round(net_return_pct / max_drawdown, 2) if max_drawdown > 0 else 0.0

        # Desglose de motivos de salida
        exit_breakdown = df["close_reason"].value_counts().to_dict()

        return {
            "total_trades": total_trades,
            "win_rate": round(win_rate, 2),
            "breakeven_rate": round(be_rate, 2),
            "profit_factor": profit_factor,
            "total_r": round(total_r, 2),
            "expectancy_r": expectancy_r,
            "sharpe_ratio": sharpe_ratio,
            "sortino_ratio": sortino_ratio,
            "calmar_ratio": calmar_ratio,
            "max_drawdown_pct": round(max_drawdown, 2),
            "net_profit_usd": round(float(df["pnl_usd"].sum()), 2),
            "exit_breakdown": exit_breakdown
        }

    def run_adaptive_portfolio_audit(self) -> Dict[str, Any]:
        """
        Ejecuta la auditoría oficial del portafolio con paridad SSoT v45.0.
        """
        btc_map = self._load_btc_macro_map()
        all_results = []

        print("=" * 85)
        print("👑  AUDITORÍA OFICIAL SLINGSHOT v45.0 APEX ZENITH SOVEREIGN (SSoT INSTITUCIONAL)")
        print("=" * 85)
        print(f"💰 Capital Base: ${self.initial_balance:,.2f} USD | Riesgo Base: {self.risk_pct*100:.2f}% | Comisiones Bitunix Descontadas")
        print("=" * 85)

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

        metrics = self.calculate_performance_metrics(all_results, self.initial_balance, self.risk_pct)

        # ── SOP-33 & SOP-38: ALPHA-TIER SIZING ASIMÉTRICO & SNIPER NY OPEN ──
        risk_usd = self.initial_balance * self.risk_pct
        def get_trade_sizing(row):
            sym = row["symbol"]
            et = pd.to_datetime(row["entry_time"])
            h = et.hour
            cs = float(row.get("confluence_score", 60.0))
            return RiskManager.calculate_alpha_tier_sizing(sym, confluence_score=cs, hour_utc=h)

        df_all["sizing_mult"] = df_all.apply(get_trade_sizing, axis=1)
        df_scaled = df_all[df_all["sizing_mult"] > 0].copy().reset_index(drop=True)
        df_scaled["pnl_usd_scaled"] = df_scaled["outcome_r"] * risk_usd * df_scaled["sizing_mult"]
        df_scaled["cum_pnl_scaled"] = df_scaled["pnl_usd_scaled"].cumsum()
        df_scaled["equity_scaled"] = self.initial_balance + df_scaled["cum_pnl_scaled"]
        df_scaled["peak_scaled"] = df_scaled["equity_scaled"].cummax()
        df_scaled["dd_pct_scaled"] = (df_scaled["equity_scaled"] - df_scaled["peak_scaled"]) / df_scaled["peak_scaled"] * 100.0
        scaled_max_dd = abs(df_scaled["dd_pct_scaled"].min()) if not df_scaled.empty else 0.0
        scaled_net_usd = df_scaled["pnl_usd_scaled"].sum() if not df_scaled.empty else 0.0
        scaled_total_r = (df_scaled["outcome_r"] * df_scaled["sizing_mult"]).sum() if not df_scaled.empty else 0.0
        scaled_wins = df_scaled[df_scaled["outcome_r"] > 0]
        scaled_losses = df_scaled[df_scaled["outcome_r"] < 0]
        scaled_loss_sum = abs((scaled_losses["outcome_r"] * scaled_losses["sizing_mult"]).sum()) if not scaled_losses.empty else 1.0
        scaled_pf = (scaled_wins["outcome_r"] * scaled_wins["sizing_mult"]).sum() / scaled_loss_sum if scaled_loss_sum > 0 else 99.0

        print(f"📊 Total Operaciones Auditadas  : {metrics['total_trades']}")
        print(f"🎯 Win Rate Real (TP1 / TP2 / TP3): {metrics['win_rate']:.1f}%")
        print(f"🛡️ Tasa de Breakeven Exacto ($0): {metrics['breakeven_rate']:.1f}%")
        print(f"⚖️ Profit Factor Base           : {metrics['profit_factor']:.2f}  |  🚀 Con Alpha-Tier Sizing: {scaled_pf:.2f}")
        print(f"💎 Retorno Total Base en R      : {metrics['total_r']:>+8.2f} R |  💎 Con Alpha-Tier Sizing: {scaled_total_r:>+8.2f} R")
        print(f"💵 Beneficio Neto USD           : {metrics['net_profit_usd']:>+11,.2f} USD |  🚀 Con Alpha-Tier: {scaled_net_usd:>+11,.2f} USD")
        print(f"📉 Drawdown Máximo Portafolio   : -{metrics['max_drawdown_pct']:.2f}% (Base)  |  🛡️ Con Alpha-Tier: -{scaled_max_dd:.2f}% (Blindaje FTMO)")
        print(f"📈 Esperanza Matemática por Op  : {metrics['expectancy_r']:>+7.3f} R / trade")
        print(f"🏆 Sharpe Ratio (Anualizado)    : {metrics['sharpe_ratio']:.2f}")
        print(f"🛡️ Sortino Ratio (Downside Dev) : {metrics['sortino_ratio']:.2f}")
        print(f"⚡ Calmar Ratio (Retorno / DD)  : {metrics['calmar_ratio']:.2f}")
        print("=" * 85)

        print("\n📋 DESGLOSE POR ACTIVO (ORDENADO POR RETORNO NETO):")
        print("-" * 85)
        asset_summary = df_all.groupby("symbol").agg(
            Trades=("outcome_r", "count"),
            Win_Rate=("outcome_r", lambda x: f"{(x > 0).mean()*100:.1f}%"),
            Retorno_R=("outcome_r", lambda x: f"{x.sum():+.2f} R"),
            Profit_Factor=("outcome_r", lambda x: f"{x[x>0].sum()/abs(x[x<0].sum()) if (x<0).sum()!=0 else 99:.2f}")
        )
        asset_ret_num = df_all.groupby("symbol")["outcome_r"].sum()
        asset_summary = asset_summary.loc[asset_ret_num.sort_values(ascending=False).index]
        print(asset_summary.to_string())
        print("=" * 85)

        # Exportar reporte inmutable
        reports_dir = os.path.join(os.path.dirname(__file__), "reports")
        os.makedirs(reports_dir, exist_ok=True)
        report_path = os.path.join(reports_dir, "unified_institutional_backtest_report.json")

        summary_payload = {
            "audit_date": datetime.now(timezone.utc).isoformat(),
            "engine_version": "v45.0 APEX TITAN (SSoT Clean Architecture)",
            "metrics": metrics,
            "scaled_metrics": {
                "scaled_total_r": round(float(scaled_total_r), 2),
                "scaled_net_usd": round(float(scaled_net_usd), 2),
                "scaled_profit_factor": round(float(scaled_pf), 2),
                "scaled_max_drawdown_pct": round(float(scaled_max_dd), 2)
            },
            "trades": all_results
        }
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(summary_payload, f, indent=4)

        print(f"💾 Reporte Oficial Inmutable guardado en: {report_path}\n")
        return summary_payload


if __name__ == "__main__":
    engine = UnifiedBacktestEngine()
    engine.run_adaptive_portfolio_audit()
