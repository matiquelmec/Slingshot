"""
engine/backtest/audit_dual_timeframe_portfolio.py
=============================================================================
AUDITORÍA DOBLE TIMEFRAME SIMULTÁNEO (15M + 1H) — SLINGSHOT v22.0 APEX
=============================================================================
Simula el escáner tal como opera en vivo:
- Monitorea 15m (Scalp) y 1h (Swing) SIMULTÁNEAMENTE para TODOS los 14 activos.
- Capital inicial: $200.00 USD
- 5% margen ($10 USD) @ 20x
- Máximo 4 operaciones con riesgo simultáneas (Slot Recycling en Fast Breakeven)
- Salidas escalonadas 60% TP1, 20% TP2, 20% TP3
- Centinela de órdenes límite en vivo
"""

import os
import sys
import glob
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from engine.indicators.polars_engine import polars_engine
from engine.indicators.structure import identify_order_blocks
from engine.strategies.smc import SMCInstitutionalStrategy
from engine.core.logger import logger

logger.setLevel("ERROR")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

ASSETS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "RENDERUSDT", "SUIUSDT", 
    "INJUSDT", "NEARUSDT", "FETUSDT", "BNBUSDT", "ATOMUSDT", 
    "PAXGUSDT", "LINKUSDT", "AVAXUSDT", "XRPUSDT"
]

def load_all_timeframes():
    data = {} # (symbol, tf) -> df
    all_ts = set()
    strategy = SMCInstitutionalStrategy()

    for sym in ASSETS:
        # Cargar 15m
        f15 = glob.glob(os.path.join(DATA_DIR, f"{sym}_15m_*.parquet"))
        if not f15: continue
        raw15 = pd.read_parquet(f15[0])
        raw15.rename(columns={'o':'open','h':'high','l':'low','c':'close','v':'volume','t':'timestamp'}, inplace=True)
        raw15['timestamp'] = pd.to_datetime(raw15['timestamp'], unit='s' if raw15['timestamp'].iloc[0] < 1e11 else 'ms')
        raw15.sort_values('timestamp', inplace=True)
        raw15.reset_index(drop=True, inplace=True)
        
        # 90 días
        max_dt = raw15['timestamp'].max()
        start_dt = max_dt - timedelta(days=90)
        df15 = raw15[raw15['timestamp'] >= start_dt].copy().reset_index(drop=True)
        
        # Computar 15m
        df15 = polars_engine.compute_indicators(df15)
        df15 = identify_order_blocks(df15)
        df15 = strategy.analyze(df15)
        df15['vol_sma'] = df15['volume'].rolling(20).mean()
        df15['rvol'] = df15['volume'] / (df15['vol_sma'] + 1e-9)
        change15 = (df15['close'] - df15['close'].shift(10)).abs()
        vol15 = (df15['close'] - df15['close'].shift(1)).abs().rolling(10).sum()
        df15['ker'] = change15 / (vol15 + 1e-9)
        data[(sym, "15m")] = df15

        # Generar 1H
        raw15.set_index('timestamp', inplace=True)
        df1h = raw15.resample('1h').agg({'open':'first','high':'max','low':'min','close':'last','volume':'sum'}).dropna().reset_index()
        df1h = df1h[df1h['timestamp'] >= start_dt].copy().reset_index(drop=True)
        df1h = polars_engine.compute_indicators(df1h)
        df1h = identify_order_blocks(df1h)
        df1h = strategy.analyze(df1h)
        df1h['vol_sma'] = df1h['volume'].rolling(20).mean()
        df1h['rvol'] = df1h['volume'] / (df1h['vol_sma'] + 1e-9)
        change1h = (df1h['close'] - df1h['close'].shift(10)).abs()
        vol1h = (df1h['close'] - df1h['close'].shift(1)).abs().rolling(10).sum()
        df1h['ker'] = change1h / (vol1h + 1e-9)
        data[(sym, "1h")] = df1h

        all_ts.update(df15['timestamp'].tolist())

    return data, sorted(list(all_ts))

def run_dual_simulation():
    data, timestamps = load_all_timeframes()
    print(f"Iniciando simulación dual (15m y 1h) con {len(timestamps)} marcas de tiempo...")

    # Mapeos rápidos
    map_15m = {sym: {row.timestamp: row for row in data[(sym, "15m")].itertuples()} for sym in ASSETS if (sym, "15m") in data}
    map_1h = {sym: {row.timestamp: row for row in data[(sym, "1h")].itertuples()} for sym in ASSETS if (sym, "1h") in data}

    initial_capital = 200.0
    equity = initial_capital
    peak_equity = initial_capital
    max_dd = 0.0
    margin_pct = 0.05
    leverage = 20
    maker_fee = 0.0002
    taker_fee = 0.0006
    slippage = 0.0002

    active_positions = {}
    pending_limits = {}
    closed_trades = []

    for current_dt in timestamps:
        hour = current_dt.hour
        is_1h_bar = (current_dt.minute == 0)

        # ── 1. GESTIÓN DE POSICIONES ACTIVAS ────────────────────────────
        closed_this_bar = []
        for key, pos in list(active_positions.items()):
            sym, tf = key
            bar = map_15m[sym].get(current_dt) if tf == "15m" else map_1h[sym].get(current_dt.floor('h') if hasattr(current_dt, 'floor') else current_dt)
            if not bar:
                bar = map_15m[sym].get(current_dt)
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
            pos_size_usd = pos["margin"] * leverage

            if direction == "LONG":
                if bl <= curr_sl:
                    if pos["hit_be"]:
                        pos["close_reason"] = "BREAKEVEN"
                        pos["pnl_usd"] += 0.0 - (pos_size_usd * (maker_fee + taker_fee))
                    else:
                        pos["close_reason"] = "STOP_LOSS"
                        loss = (pos_size_usd * rem_pos) * (risk / entry) + (pos_size_usd * (taker_fee + slippage))
                        pos["pnl_usd"] -= loss

                    equity += pos["pnl_usd"]
                    closed_this_bar.append((key, pos))
                    continue

                if not pos["hit_be"] and bh >= be_target:
                    pos["hit_be"] = True
                    pos["curr_sl"] = entry

                if not pos["hit_tp1"] and bh >= tp1:
                    pos["hit_tp1"] = True
                    pos["hit_be"] = True
                    pos["curr_sl"] = entry
                    gain = (pos_size_usd * 0.60) * ((tp1 - entry) / entry) - ((pos_size_usd * 0.60) * maker_fee)
                    pos["pnl_usd"] += gain
                    pos["rem_pos"] -= 0.60

                if pos["hit_tp1"] and not pos["hit_tp2"] and bh >= tp2:
                    pos["hit_tp2"] = True
                    pos["curr_sl"] = tp1
                    gain = (pos_size_usd * 0.20) * ((tp2 - entry) / entry) - ((pos_size_usd * 0.20) * maker_fee)
                    pos["pnl_usd"] += gain
                    pos["rem_pos"] -= 0.20

                if pos["hit_tp2"] and bh >= tp3:
                    gain = (pos_size_usd * 0.20) * ((tp3 - entry) / entry) - ((pos_size_usd * 0.20) * maker_fee)
                    pos["pnl_usd"] += gain
                    pos["rem_pos"] = 0.0
                    pos["close_reason"] = "TAKE_PROFIT_3"
                    equity += pos["pnl_usd"]
                    closed_this_bar.append((key, pos))
                    continue

            else: # SHORT
                if bh >= curr_sl:
                    if pos["hit_be"]:
                        pos["close_reason"] = "BREAKEVEN"
                        pos["pnl_usd"] += 0.0 - (pos_size_usd * (maker_fee + taker_fee))
                    else:
                        pos["close_reason"] = "STOP_LOSS"
                        loss = (pos_size_usd * rem_pos) * (risk / entry) + (pos_size_usd * (taker_fee + slippage))
                        pos["pnl_usd"] -= loss

                    equity += pos["pnl_usd"]
                    closed_this_bar.append((key, pos))
                    continue

                if not pos["hit_be"] and bl <= be_target:
                    pos["hit_be"] = True
                    pos["curr_sl"] = entry

                if not pos["hit_tp1"] and bl <= tp1:
                    pos["hit_tp1"] = True
                    pos["hit_be"] = True
                    pos["curr_sl"] = entry
                    gain = (pos_size_usd * 0.60) * ((entry - tp1) / entry) - ((pos_size_usd * 0.60) * maker_fee)
                    pos["pnl_usd"] += gain
                    pos["rem_pos"] -= 0.60

                if pos["hit_tp1"] and not pos["hit_tp2"] and bl <= tp2:
                    pos["hit_tp2"] = True
                    pos["curr_sl"] = tp1
                    gain = (pos_size_usd * 0.20) * ((entry - tp2) / entry) - ((pos_size_usd * 0.20) * maker_fee)
                    pos["pnl_usd"] += gain
                    pos["rem_pos"] -= 0.20

                if pos["hit_tp2"] and bl <= tp3:
                    gain = (pos_size_usd * 0.20) * ((entry - tp3) / entry) - ((pos_size_usd * 0.20) * maker_fee)
                    pos["pnl_usd"] += gain
                    pos["rem_pos"] = 0.0
                    pos["close_reason"] = "TAKE_PROFIT_3"
                    equity += pos["pnl_usd"]
                    closed_this_bar.append((key, pos))
                    continue

        for key, pos in closed_this_bar:
            pos["exit_time"] = current_dt
            closed_trades.append(pos)
            del active_positions[key]

        # ── 2. AUDITORÍA DEL CENTINELA DE ÓRDENES LÍMITE ─────────────────
        unprotected_risk_count = sum(1 for p in active_positions.values() if not p["hit_be"])
        if unprotected_risk_count >= 4:
            pending_limits.clear()

        cancelled_limits = []
        for key, ord_info in list(pending_limits.items()):
            sym, tf = key
            bar = map_15m[sym].get(current_dt)
            if not bar: continue

            bh = float(bar.high)
            bl = float(bar.low)
            direction = ord_info["direction"]
            entry = ord_info["entry"]
            sl = ord_info["sl"]
            tp1 = ord_info["tp1"]
            ord_info["age_bars"] += 1

            # Missed target kill-switch
            if (direction == "LONG" and bh >= tp1) or (direction == "SHORT" and bl <= tp1):
                cancelled_limits.append(key)
                continue

            # Pre-entry SL breach
            if (direction == "LONG" and bl <= sl) or (direction == "SHORT" and bh >= sl):
                cancelled_limits.append(key)
                continue

            # TTL
            max_age = 12 if tf == "15m" else 24
            if ord_info["age_bars"] > max_age:
                cancelled_limits.append(key)
                continue

            # Fill
            filled = (direction == "LONG" and bl <= entry) or (direction == "SHORT" and bh >= entry)
            if filled:
                if unprotected_risk_count < 4:
                    margin = max(5.0, equity * margin_pct)
                    active_positions[key] = {
                        "symbol": sym,
                        "interval": tf,
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
                cancelled_limits.append(key)

        for key in cancelled_limits:
            if key in pending_limits:
                del pending_limits[key]

        # ── 3. DETECCIÓN DE OPORTUNIDADES (15M y 1H) ─────────────────────
        if unprotected_risk_count < 4 and 7 <= hour <= 19:
            timeframes_to_check = ["15m"]
            if is_1h_bar:
                timeframes_to_check.append("1h")

            for tf in timeframes_to_check:
                for sym in ASSETS:
                    key = (sym, tf)
                    if key in active_positions or key in pending_limits:
                        continue

                    # Solo 1 trade por activo a la vez
                    if any(k[0] == sym for k in active_positions.keys()) or any(k[0] == sym for k in pending_limits.keys()):
                        continue

                    df = data.get(key)
                    if df is None: continue

                    cur_map = map_15m[sym] if tf == "15m" else map_1h[sym]
                    bar = cur_map.get(current_dt)
                    if not bar: continue

                    idx = bar.Index
                    if idx < 30 or idx >= len(df) - 10: continue

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
                    atr_sl_mult = 0.60 if tf == "1h" else 0.30

                    if direction == "LONG":
                        fvg_low = float(df.iloc[idx-2]['high'])
                        fvg_high = float(df.iloc[idx]['low'])
                        entry = fvg_low + (fvg_high - fvg_low) * 0.382 if (tf == "1h" and fvg_high > fvg_low) else fvg_low
                        sl = float(min(df.iloc[idx-1]['low'], df.iloc[idx]['low'])) - (atr * atr_sl_mult)
                        risk = entry - sl
                        if risk <= 0 or (risk / entry) > 0.04: continue
                        be_target = entry + (risk * 1.2)
                        tp1 = entry + (risk * 1.5)
                        tp2 = entry + (risk * 2.5)
                        tp3 = entry + (risk * (4.0 if tf == "1h" else 3.5))
                    else:
                        fvg_high = float(df.iloc[idx-2]['low'])
                        fvg_low = float(df.iloc[idx]['low'])
                        entry = fvg_high - (fvg_high - fvg_low) * 0.382 if (tf == "1h" and fvg_high > fvg_low) else fvg_high
                        sl = float(max(df.iloc[idx-1]['high'], df.iloc[idx]['high'])) + (atr * atr_sl_mult)
                        risk = sl - entry
                        if risk <= 0 or (risk / entry) > 0.04: continue
                        be_target = entry - (risk * 1.2)
                        tp1 = entry - (risk * 1.5)
                        tp2 = entry - (risk * 2.5)
                        tp3 = entry - (risk * (4.0 if tf == "1h" else 3.5))

                    pending_limits[key] = {
                        "symbol": sym,
                        "interval": tf,
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

        if equity > peak_equity:
            peak_equity = equity
        dd = (peak_equity - equity) / peak_equity * 100
        if dd > max_dd:
            max_dd = dd

    df_trades = pd.DataFrame(closed_trades)
    total_trades = len(df_trades)
    wins = df_trades[df_trades["pnl_usd"] > 0]
    losses = df_trades[df_trades["pnl_usd"] < -0.1]
    be_trades = df_trades[(df_trades["pnl_usd"] >= -0.1) & (df_trades["pnl_usd"] <= 0.05)]
    net_profit_usd = equity - initial_capital
    roi_pct = (net_profit_usd / initial_capital) * 100

    print("\n" + "="*85)
    print("🎯 INFORME DE RENDIMIENTO DUAL (15M SCALP + 1H SWING) — 90 DÍAS")
    print("="*85)
    print(f"💰 Capital Inicial               : ${initial_capital:.2f} USD")
    print(f"💎 Capital Final                 : ${equity:.2f} USD")
    print(f"💵 Ganancia Neta Total           : +${net_profit_usd:.2f} USD (+{roi_pct:.2f}%)")
    print(f"📊 Total de Operaciones          : {total_trades}")
    print(f"🏆 Operaciones Ganadoras (Wins)  : {len(wins)} ({(len(wins)/total_trades)*100:.1f}%)")
    print(f"🛡️ Operaciones en Breakeven ($0) : {len(be_trades)} ({(len(be_trades)/total_trades)*100:.1f}%)")
    print(f"📉 Drawdown Máximo del Portafolio: -{max_dd:.2f}%")
    print("="*85)

    print("\n📋 DESGLOSE POR TEMPORALIDAD:")
    print("-" * 85)
    by_tf = df_trades.groupby("interval").agg(
        Trades=("pnl_usd", "count"),
        Wins=("pnl_usd", lambda x: (x > 0).sum()),
        Net_USD=("pnl_usd", "sum")
    ).reset_index()
    by_tf["Win_Rate"] = (by_tf["Wins"] / by_tf["Trades"] * 100).map("{:.1f}%".format)
    by_tf["Net_USD"] = by_tf["Net_USD"].map("+${:.2f}".format)
    print(by_tf.to_string(index=False))

    print("\n📋 DESGLOSE POR ACTIVO:")
    print("-" * 85)
    by_asset = df_trades.groupby("symbol").agg(
        Trades=("pnl_usd", "count"),
        Wins=("pnl_usd", lambda x: (x > 0).sum()),
        Net_USD=("pnl_usd", "sum")
    ).reset_index()
    by_asset["Win_Rate"] = (by_asset["Wins"] / by_asset["Trades"] * 100).map("{:.1f}%".format)
    by_asset.sort_values(by="Net_USD", ascending=False, inplace=True)
    print(by_asset.to_string(index=False))
    print("="*85 + "\n")

if __name__ == "__main__":
    run_dual_simulation()
