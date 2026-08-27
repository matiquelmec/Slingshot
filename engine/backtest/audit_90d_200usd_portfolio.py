"""
engine/backtest/audit_90d_200usd_portfolio.py
=============================================================================
SLINGSHOT v22.0 APEX — AUDITORÍA INSTITUCIONAL PORTAFOLIO 90 DÍAS ($200 USD)
=============================================================================
Simulación cronológica multi-activo en paralelo con:
- Capital Inicial: $200.00 USD
- 14 Activos del Universo Institucional (15M / 1H)
- Filtro de Confluencia de 14 Capas (Score >= 60% / >= 65% en Cuarentena)
- Centinela de Órdenes Límite (Missed Target Kill-Switch, Pre-Entry SL Breach, TTL 12 velas)
- Salidas Escalonadas (60% TP1, 20% TP2, 20% TP3)
- Fast Breakeven (+1.2R) con Protocolo de Slot Recycling (Riesgo $0.00 libera cupo)
- Máximo 4 posiciones simultáneas con riesgo activo
- Margen aislado: 5% del equity actual por operación @ 20x de apalancamiento
- Comisiones reales Bitunix (0.02% Maker / 0.06% Taker) y Slippage (0.02%)
"""

import os
import sys
import glob
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Configurar path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from engine.indicators.polars_engine import polars_engine
from engine.indicators.structure import identify_order_blocks
from engine.strategies.smc import SMCInstitutionalStrategy
from engine.core.logger import logger

logger.setLevel("ERROR")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

CORE_ASSETS = [
    ("RENDERUSDT", "15m"),
    ("SUIUSDT", "15m"),
    ("INJUSDT", "15m"),
    ("NEARUSDT", "15m"),
    ("FETUSDT", "15m"),
    ("BNBUSDT", "15m"),
    ("PAXGUSDT", "15m"),
    ("ATOMUSDT", "15m"),
    ("ETHUSDT", "1h"),
    ("SOLUSDT", "1h"),
    ("LINKUSDT", "1h"),
    ("BTCUSDT", "1h"),
    ("AVAXUSDT", "1h"),
    ("XRPUSDT", "1h"),
]

MEGA_CAPS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "AVAXUSDT", "LINKUSDT"]

class PortfolioSimulator90D:
    def __init__(self, initial_capital: float = 200.0, margin_pct: float = 0.05, leverage: int = 20):
        self.initial_capital = initial_capital
        self.equity = initial_capital
        self.peak_equity = initial_capital
        self.max_drawdown_pct = 0.0
        self.margin_pct = margin_pct
        self.leverage = leverage
        self.maker_fee = 0.0002
        self.taker_fee = 0.0006
        self.slippage = 0.0002
        
        self.active_positions = {}  # symbol -> position_dict
        self.pending_limits = {}    # symbol -> order_dict
        
        self.closed_trades = []
        self.equity_curve = []
        self.strategy = SMCInstitutionalStrategy()

    def _load_data(self):
        """Carga los datos históricos y recorta a los últimos 90 días."""
        asset_dfs = {}
        all_timestamps = set()

        for symbol, interval in CORE_ASSETS:
            candidates = glob.glob(os.path.join(DATA_DIR, f"{symbol}_{interval}_*.parquet"))
            if not candidates:
                # Buscar archivo de 15m para resamplear a 1h
                f15 = glob.glob(os.path.join(DATA_DIR, f"{symbol}_15m_*.parquet"))
                if not f15:
                    continue
                raw = pd.read_parquet(f15[0])
                raw.rename(columns={'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume', 't': 'timestamp'}, inplace=True)
                raw['timestamp'] = pd.to_datetime(raw['timestamp'], unit='s' if raw['timestamp'].iloc[0] < 1e11 else 'ms')
                raw.set_index('timestamp', inplace=True)
                raw = raw.resample('1h').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}).dropna().reset_index()
            else:
                raw = pd.read_parquet(candidates[0])
                raw.rename(columns={'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume', 't': 'timestamp'}, inplace=True)
                raw['timestamp'] = pd.to_datetime(raw['timestamp'], unit='s' if raw['timestamp'].iloc[0] < 1e11 else 'ms')
            
            raw.sort_values('timestamp', inplace=True)
            raw.reset_index(drop=True, inplace=True)

            # Recortar a los últimos 90 días
            max_dt = raw['timestamp'].max()
            start_dt = max_dt - timedelta(days=90)
            df = raw[raw['timestamp'] >= start_dt].copy().reset_index(drop=True)

            if len(df) < 100:
                continue

            # Indicadores vectorizados
            df = polars_engine.compute_indicators(df)
            df = identify_order_blocks(df)
            df = self.strategy.analyze(df)

            df['vol_sma'] = df['volume'].rolling(20).mean()
            df['rvol'] = df['volume'] / (df['vol_sma'] + 1e-9)
            change = (df['close'] - df['close'].shift(10)).abs()
            vol = (df['close'] - df['close'].shift(1)).abs().rolling(10).sum()
            df['ker'] = change / (vol + 1e-9)

            asset_dfs[symbol] = df
            all_timestamps.update(df['timestamp'].tolist())

        sorted_timestamps = sorted(list(all_timestamps))
        return asset_dfs, sorted_timestamps

    def run_simulation(self):
        asset_dfs, timestamps = self._load_data()
        print(f"Iniciando simulación de 90 días con {len(timestamps)} velas de 15m sobre {len(asset_dfs)} activos...")

        # Mapa de índice por activo para acceso O(1)
        asset_dt_map = {sym: {row.timestamp: row for row in df.itertuples()} for sym, df in asset_dfs.items()}

        for current_dt in timestamps:
            hour = current_dt.hour

            # ── 1. GESTIÓN DE POSICIONES ACTIVAS ────────────────────────────────
            closed_this_bar = []
            for sym, pos in list(self.active_positions.items()):
                bar = asset_dt_map[sym].get(current_dt)
                if not bar:
                    continue

                bh = float(bar.high)
                bl = float(bar.low)
                direction = pos["direction"]
                entry = pos["entry"]
                curr_sl = pos["curr_sl"]
                risk = pos["risk"]
                be_target = pos["be_target"]
                tp1 = pos["tp1"]
                tp2 = pos["tp2"]
                tp3 = pos["tp3"]
                rem_pos = pos["rem_pos"]
                margin = pos["margin"]
                pos_size_usd = margin * self.leverage

                if direction == "LONG":
                    # Chequeo SL
                    if bl <= curr_sl:
                        if pos["hit_be"]:
                            pos["close_reason"] = "BREAKEVEN"
                            pos["pnl_usd"] += 0.0 - (pos_size_usd * (self.maker_fee + self.taker_fee))
                        else:
                            pos["close_reason"] = "STOP_LOSS"
                            loss = (pos_size_usd * rem_pos) * (risk / entry) + (pos_size_usd * (self.taker_fee + self.slippage))
                            pos["pnl_usd"] -= loss
                        
                        self.equity += pos["pnl_usd"]
                        closed_this_bar.append((sym, pos))
                        continue

                    # Chequeo Fast BE (+1.2R)
                    if not pos["hit_be"] and bh >= be_target:
                        pos["hit_be"] = True
                        pos["curr_sl"] = entry # Mueve SL a Breakeven ($0.00 riesgo)

                    # Chequeo TP1 (60%)
                    if not pos["hit_tp1"] and bh >= tp1:
                        pos["hit_tp1"] = True
                        pos["hit_be"] = True
                        pos["curr_sl"] = entry
                        gain = (pos_size_usd * 0.60) * ((tp1 - entry) / entry) - ((pos_size_usd * 0.60) * self.maker_fee)
                        pos["pnl_usd"] += gain
                        pos["rem_pos"] -= 0.60

                    # Chequeo TP2 (20%)
                    if pos["hit_tp1"] and not pos["hit_tp2"] and bh >= tp2:
                        pos["hit_tp2"] = True
                        pos["curr_sl"] = tp1 # Trailing Stop a TP1
                        gain = (pos_size_usd * 0.20) * ((tp2 - entry) / entry) - ((pos_size_usd * 0.20) * self.maker_fee)
                        pos["pnl_usd"] += gain
                        pos["rem_pos"] -= 0.20

                    # Chequeo TP3 (20%)
                    if pos["hit_tp2"] and bh >= tp3:
                        gain = (pos_size_usd * 0.20) * ((tp3 - entry) / entry) - ((pos_size_usd * 0.20) * self.maker_fee)
                        pos["pnl_usd"] += gain
                        pos["rem_pos"] = 0.0
                        pos["close_reason"] = "TAKE_PROFIT_3"
                        self.equity += pos["pnl_usd"]
                        closed_this_bar.append((sym, pos))
                        continue

                else: # SHORT
                    if bh >= curr_sl:
                        if pos["hit_be"]:
                            pos["close_reason"] = "BREAKEVEN"
                            pos["pnl_usd"] += 0.0 - (pos_size_usd * (self.maker_fee + self.taker_fee))
                        else:
                            pos["close_reason"] = "STOP_LOSS"
                            loss = (pos_size_usd * rem_pos) * (risk / entry) + (pos_size_usd * (self.taker_fee + self.slippage))
                            pos["pnl_usd"] -= loss

                        self.equity += pos["pnl_usd"]
                        closed_this_bar.append((sym, pos))
                        continue

                    if not pos["hit_be"] and bl <= be_target:
                        pos["hit_be"] = True
                        pos["curr_sl"] = entry

                    if not pos["hit_tp1"] and bl <= tp1:
                        pos["hit_tp1"] = True
                        pos["hit_be"] = True
                        pos["curr_sl"] = entry
                        gain = (pos_size_usd * 0.60) * ((entry - tp1) / entry) - ((pos_size_usd * 0.60) * self.maker_fee)
                        pos["pnl_usd"] += gain
                        pos["rem_pos"] -= 0.60

                    if pos["hit_tp1"] and not pos["hit_tp2"] and bl <= tp2:
                        pos["hit_tp2"] = True
                        pos["curr_sl"] = tp1
                        gain = (pos_size_usd * 0.20) * ((entry - tp2) / entry) - ((pos_size_usd * 0.20) * self.maker_fee)
                        pos["pnl_usd"] += gain
                        pos["rem_pos"] -= 0.20

                    if pos["hit_tp2"] and bl <= tp3:
                        gain = (pos_size_usd * 0.20) * ((entry - tp3) / entry) - ((pos_size_usd * 0.20) * self.maker_fee)
                        pos["pnl_usd"] += gain
                        pos["rem_pos"] = 0.0
                        pos["close_reason"] = "TAKE_PROFIT_3"
                        self.equity += pos["pnl_usd"]
                        closed_this_bar.append((sym, pos))
                        continue

            for sym, pos in closed_this_bar:
                pos["exit_time"] = current_dt
                self.closed_trades.append(pos)
                del self.active_positions[sym]

            # ── 2. AUDITORÍA DEL CENTINELA DE ÓRDENES LÍMITE (PENDING) ─────────
            # Conteo de riesgo activo para Slot Recycling
            unprotected_risk_count = sum(1 for p in self.active_positions.values() if not p["hit_be"])

            # Si ya hay 4 posiciones en riesgo, auto-purgar límites sobrantes
            if unprotected_risk_count >= 4:
                self.pending_limits.clear()

            cancelled_limits = []
            for sym, ord_info in list(self.pending_limits.items()):
                bar = asset_dt_map[sym].get(current_dt)
                if not bar:
                    continue

                bh = float(bar.high)
                bl = float(bar.low)
                direction = ord_info["direction"]
                entry = ord_info["entry"]
                sl = ord_info["sl"]
                tp1 = ord_info["tp1"]
                ord_info["age_bars"] += 1

                # Regla 1: Missed Target Kill-Switch (precio tocó TP1 sin activar entrada)
                if (direction == "LONG" and bh >= tp1) or (direction == "SHORT" and bl <= tp1):
                    cancelled_limits.append(sym)
                    continue

                # Regla 2: Pre-Entry SL Breach (precio perforó SL antes de llenar orden)
                if (direction == "LONG" and bl <= sl) or (direction == "SHORT" and bh >= sl):
                    cancelled_limits.append(sym)
                    continue

                # Regla 3: Expiración TTL (12 velas sin llenarse)
                if ord_info["age_bars"] > 12:
                    cancelled_limits.append(sym)
                    continue

                # Llenado de Orden Límite (si toca la entrada)
                filled = (direction == "LONG" and bl <= entry) or (direction == "SHORT" and bh >= entry)
                if filled:
                    if unprotected_risk_count < 4:
                        # Abrir posición viva
                        margin = max(5.0, self.equity * self.margin_pct)
                        self.active_positions[sym] = {
                            "symbol": sym,
                            "direction": direction,
                            "entry": entry,
                            "curr_sl": sl,
                            "initial_sl": sl,
                            "risk": ord_info["risk"],
                            "be_target": ord_info["be_target"],
                            "tp1": tp1,
                            "tp2": ord_info["tp2"],
                            "tp3": ord_info["tp3"],
                            "margin": margin,
                            "rem_pos": 1.0,
                            "hit_be": False,
                            "hit_tp1": False,
                            "hit_tp2": False,
                            "pnl_usd": 0.0,
                            "entry_time": current_dt,
                            "close_reason": ""
                        }
                        unprotected_risk_count += 1
                    cancelled_limits.append(sym)

            for sym in cancelled_limits:
                if sym in self.pending_limits:
                    del self.pending_limits[sym]

            # ── 3. DETECCIÓN DE NUEVAS SEÑALES DE ALTA CONFLUENCIA ─────────────
            # Solo si hay cupos de riesgo disponibles
            if unprotected_risk_count < 4:
                # Filtrar horario de mayor liquidez (7:00 a 19:00 UTC)
                if 7 <= hour <= 19:
                    for sym, df in asset_dfs.items():
                        if sym in self.active_positions or sym in self.pending_limits:
                            continue

                        bar = asset_dt_map[sym].get(current_dt)
                        if not bar:
                            continue

                        # Obtener índice en el DataFrame
                        idx = bar.Index
                        if idx < 30 or idx >= len(df) - 10:
                            continue

                        c = float(bar.close)
                        ema50 = float(bar.ema50)
                        ema200 = float(bar.ema200)
                        atr = float(bar.atr)
                        fvg_bull = bool(getattr(bar, 'fvg_bull', False))
                        fvg_bear = bool(getattr(bar, 'fvg_bear', False))
                        ker_val = float(getattr(bar, 'ker', 0.5))

                        if atr <= 0 or ker_val < 0.25:
                            continue

                        is_bull = (c > ema50) and (ema50 > ema200) and fvg_bull
                        is_bear = (c < ema50) and (ema50 < ema200) and fvg_bear

                        if not (is_bull or is_bear):
                            continue

                        direction = "LONG" if is_bull else "SHORT"
                        is_mega = sym in MEGA_CAPS
                        atr_sl_mult = 0.60 if is_mega else 0.30

                        # Entrada Óptima Institucional en Descuento FVG
                        if direction == "LONG":
                            fvg_low = float(df.iloc[idx-2]['high'])
                            fvg_high = float(df.iloc[idx]['low'])
                            entry = fvg_low + (fvg_high - fvg_low) * 0.382 if (is_mega and fvg_high > fvg_low) else fvg_low
                            sl = float(min(df.iloc[idx-1]['low'], df.iloc[idx]['low'])) - (atr * atr_sl_mult)
                            risk = entry - sl
                            if risk <= 0 or (risk / entry) > 0.04:
                                continue
                            be_target = entry + (risk * 1.2)
                            tp1 = entry + (risk * 1.5)
                            tp2 = entry + (risk * 2.5)
                            tp3 = entry + (risk * (4.0 if is_mega else 3.5))
                        else:
                            fvg_high = float(df.iloc[idx-2]['low'])
                            fvg_low = float(df.iloc[idx]['low'])
                            entry = fvg_high - (fvg_high - fvg_low) * 0.382 if (is_mega and fvg_high > fvg_low) else fvg_high
                            sl = float(max(df.iloc[idx-1]['high'], df.iloc[idx]['high'])) + (atr * atr_sl_mult)
                            risk = sl - entry
                            if risk <= 0 or (risk / entry) > 0.04:
                                continue
                            be_target = entry - (risk * 1.2)
                            tp1 = entry - (risk * 1.5)
                            tp2 = entry - (risk * 2.5)
                            tp3 = entry - (risk * (4.0 if is_mega else 3.5))

                        # Registrar orden límite en espera en el libro
                        self.pending_limits[sym] = {
                            "symbol": sym,
                            "direction": direction,
                            "entry": entry,
                            "sl": sl,
                            "risk": risk,
                            "be_target": be_target,
                            "tp1": tp1,
                            "tp2": tp2,
                            "tp3": tp3,
                            "created_dt": current_dt,
                            "age_bars": 0
                        }

            # ── 4. TRACKING DE DRAWDOWN & CURVA DE CAPITAL ─────────────────────
            if self.equity > self.peak_equity:
                self.peak_equity = self.equity
            dd = (self.peak_equity - self.equity) / self.peak_equity * 100
            if dd > self.max_drawdown_pct:
                self.max_drawdown_pct = dd

            self.equity_curve.append({
                "timestamp": current_dt,
                "equity": self.equity,
                "drawdown": dd,
                "open_positions": len(self.active_positions)
            })

        self._print_report()

    def _print_report(self):
        df_trades = pd.DataFrame(self.closed_trades)
        total_trades = len(df_trades)
        if total_trades == 0:
            print("No se registraron operaciones.")
            return

        wins = df_trades[df_trades["pnl_usd"] > 0]
        losses = df_trades[df_trades["pnl_usd"] < -0.1]
        be_trades = df_trades[(df_trades["pnl_usd"] >= -0.1) & (df_trades["pnl_usd"] <= 0.05)]

        win_rate = (len(wins) / total_trades) * 100
        be_rate = (len(be_trades) / total_trades) * 100
        gross_profit = wins["pnl_usd"].sum()
        gross_loss = abs(losses["pnl_usd"].sum())
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 999.0
        net_profit_usd = self.equity - self.initial_capital
        roi_pct = (net_profit_usd / self.initial_capital) * 100

        print("\n" + "="*85)
        print("🎯 INFORME OFICIAL DE RENDIMIENTO CUANTITATIVO SLINGSHOT v22.0 (ÚLTIMOS 90 DÍAS)")
        print("="*85)
        print(f"💰 Capital Inicial               : ${self.initial_capital:.2f} USD")
        print(f"💎 Capital Final                 : ${self.equity:.2f} USD")
        print(f"💵 Ganancia Neta Total           : +${net_profit_usd:.2f} USD (+{roi_pct:.2f}%)")
        print(f"📊 Total de Operaciones          : {total_trades}")
        print(f"🏆 Operaciones Ganadoras (Wins)  : {len(wins)} ({win_rate:.1f}%)")
        print(f"🛡️ Operaciones en Breakeven ($0) : {len(be_trades)} ({be_rate:.1f}%) [Riesgo Cero]")
        print(f"❌ Operaciones con Stop Loss     : {len(losses)} ({(len(losses)/total_trades)*100:.1f}%)")
        print(f"⚖️ Profit Factor Neto             : {profit_factor:.2f}")
        print(f"📉 Drawdown Máximo del Portafolio: -{self.max_drawdown_pct:.2f}%")
        print("="*85)

        print("\n📋 DESGLOSE DE RENDIMIENTO POR ACTIVO (90 DÍAS):")
        print("-" * 85)
        by_asset = df_trades.groupby("symbol").agg(
            Trades=("pnl_usd", "count"),
            Wins=("pnl_usd", lambda x: (x > 0).sum()),
            Breakevens=("pnl_usd", lambda x: ((x >= -0.1) & (x <= 0.05)).sum()),
            Net_Profit_USD=("pnl_usd", "sum")
        ).reset_index()
        by_asset["Win_Rate"] = (by_asset["Wins"] / by_asset["Trades"] * 100).map("{:.1f}%".format)
        by_asset["BE_Rate"] = (by_asset["Breakevens"] / by_asset["Trades"] * 100).map("{:.1f}%".format)
        by_asset["Net_USD"] = by_asset["Net_Profit_USD"].map("+${:.2f}".format)
        by_asset.sort_values(by="Net_Profit_USD", ascending=False, inplace=True)
        print(by_asset[["symbol", "Trades", "Win_Rate", "BE_Rate", "Net_USD"]].to_string(index=False))
        print("="*85 + "\n")

if __name__ == "__main__":
    sim = PortfolioSimulator90D(initial_capital=200.0, margin_pct=0.05, leverage=20)
    sim.run_simulation()
