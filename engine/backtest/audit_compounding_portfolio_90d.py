"""
engine/backtest/audit_compounding_portfolio_90d.py
=============================================================================
AUDITORÍA CON INTERÉS COMPUESTO DINÁMICO (5% DEL EQUITY ACTUAL @ 20x)
=============================================================================
Simula el crecimiento exponencial del capital reinvirtiendo ganancias:
- Capital Inicial: $200.00 USD
- Margen Dinámico: 5% del Balance Total en cada trade (Compounding)
- Apalancamiento: 20x
- Activos Líderes de Alta Confluencia (RENDER, SUI, NEAR, INJ, LINK, ETH, ATOM, FET)
- Salidas Escalonadas (60% TP1, 20% TP2, 20% TP3)
- Fast Breakeven (+1.2R) con Slot Recycling
- Fricción real de Bitunix (Maker 0.02%, Taker 0.06%, Slippage 0.02%)
"""

import os
import sys
import glob
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

STAR_ASSETS = ["RENDERUSDT", "SUIUSDT", "NEARUSDT", "INJUSDT", "LINKUSDT", "ETHUSDT", "ATOMUSDT", "FETUSDT"]

def run_compound_simulation():
    initial_capital = 200.0
    equity = initial_capital
    peak_equity = initial_capital
    max_dd = 0.0
    
    margin_pct = 0.05
    leverage = 20
    maker_fee = 0.0002
    taker_fee = 0.0006
    slippage = 0.0002

    # Cargar y sincronizar datos de 90 días
    asset_dfs = {}
    all_ts = set()

    for sym in STAR_ASSETS:
        f = glob.glob(os.path.join(DATA_DIR, f"{sym}_15m_*.parquet"))
        if not f: continue
        raw = pd.read_parquet(f[0])
        raw.rename(columns={'o':'open','h':'high','l':'low','c':'close','v':'volume','t':'timestamp'}, inplace=True)
        raw['timestamp'] = pd.to_datetime(raw['timestamp'], unit='s' if raw['timestamp'].iloc[0] < 1e11 else 'ms')
        raw.sort_values('timestamp', inplace=True)
        
        max_dt = raw['timestamp'].max()
        start_dt = max_dt - timedelta(days=90)
        df = raw[raw['timestamp'] >= start_dt].copy().reset_index(drop=True)
        
        df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
        df['tr'] = np.maximum(df['high'] - df['low'], np.maximum((df['high'] - df['close'].shift(1)).abs(), (df['low'] - df['close'].shift(1)).abs()))
        df['atr'] = df['tr'].rolling(14).mean()
        df['fvg_bull'] = (df['low'] > df['high'].shift(2))
        df['fvg_bear'] = (df['high'] < df['low'].shift(2))
        
        # Volumen y KER
        df['vol_sma'] = df['volume'].rolling(20).mean()
        df['rvol'] = df['volume'] / (df['vol_sma'] + 1e-9)
        change = (df['close'] - df['close'].shift(10)).abs()
        vol = (df['close'] - df['close'].shift(1)).abs().rolling(10).sum()
        df['ker'] = change / (vol + 1e-9)
        
        asset_dfs[sym] = df
        all_ts.update(df['timestamp'].tolist())

    timestamps = sorted(list(all_ts))
    map_bars = {sym: {row.timestamp: row for row in df.itertuples()} for sym, df in asset_dfs.items()}

    active_positions = {}
    pending_limits = {}
    closed_trades = []
    milestones = []

    for current_dt in timestamps:
        hour = current_dt.hour

        # ── 1. GESTIÓN DE POSICIONES ACTIVAS ────────────────────────────
        closed_this_bar = []
        for sym, pos in list(active_positions.items()):
            bar = map_bars[sym].get(current_dt)
            if not bar: continue

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
                    closed_this_bar.append((sym, pos))
                    continue

                if not pos["hit_be"] and bh >= be_target:
                    pos["hit_be"] = True
                    curr_sl = entry
                    pos["curr_sl"] = entry

                if not pos["hit_tp1"] and bh >= tp1:
                    pos["hit_tp1"] = True
                    pos["hit_be"] = True
                    curr_sl = entry
                    pos["curr_sl"] = entry
                    gain = (pos_size_usd * 0.60) * ((tp1 - entry) / entry) - ((pos_size_usd * 0.60) * maker_fee)
                    pos["pnl_usd"] += gain
                    pos["rem_pos"] -= 0.60

                if pos["hit_tp1"] and not pos["hit_tp2"] and bh >= tp2:
                    pos["hit_tp2"] = True
                    curr_sl = tp1
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
                    closed_this_bar.append((sym, pos))
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
                    closed_this_bar.append((sym, pos))
                    continue

                if not pos["hit_be"] and bl <= be_target:
                    pos["hit_be"] = True
                    curr_sl = entry
                    pos["curr_sl"] = entry

                if not pos["hit_tp1"] and bl <= tp1:
                    pos["hit_tp1"] = True
                    pos["hit_be"] = True
                    curr_sl = entry
                    pos["curr_sl"] = entry
                    gain = (pos_size_usd * 0.60) * ((entry - tp1) / entry) - ((pos_size_usd * 0.60) * maker_fee)
                    pos["pnl_usd"] += gain
                    pos["rem_pos"] -= 0.60

                if pos["hit_tp1"] and not pos["hit_tp2"] and bl <= tp2:
                    pos["hit_tp2"] = True
                    curr_sl = tp1
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
                    closed_this_bar.append((sym, pos))
                    continue

        for sym, pos in closed_this_bar:
            pos["exit_time"] = current_dt
            pos["equity_after"] = equity
            closed_trades.append(pos)
            del active_positions[sym]

        # ── 2. AUDITORÍA DEL CENTINELA DE ÓRDENES LÍMITE ─────────────────
        unprotected_risk_count = sum(1 for p in active_positions.values() if not p["hit_be"])
        if unprotected_risk_count >= 4:
            pending_limits.clear()

        cancelled_limits = []
        for sym, ord_info in list(pending_limits.items()):
            bar = map_bars[sym].get(current_dt)
            if not bar: continue

            bh = float(bar.high)
            bl = float(bar.low)
            direction = ord_info["direction"]
            entry = ord_info["entry"]
            sl = ord_info["sl"]
            tp1 = ord_info["tp1"]
            ord_info["age_bars"] += 1

            # Missed Target Kill-Switch
            if (direction == "LONG" and bh >= tp1) or (direction == "SHORT" and bl <= tp1):
                cancelled_limits.append(sym)
                continue

            # Pre-entry SL Breach
            if (direction == "LONG" and bl <= sl) or (direction == "SHORT" and bh >= sl):
                cancelled_limits.append(sym)
                continue

            # TTL 12 velas
            if ord_info["age_bars"] > 12:
                cancelled_limits.append(sym)
                continue

            # Llenado con Margen Compuesto Dinámico (5% del Equity Actual)
            filled = (direction == "LONG" and bl <= entry) or (direction == "SHORT" and bh >= entry)
            if filled:
                if unprotected_risk_count < 4:
                    dynamic_margin = max(5.0, equity * margin_pct)
                    active_positions[sym] = {
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
                        "margin": dynamic_margin, # Margen compuesto
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
            if sym in pending_limits:
                del pending_limits[sym]

        # ── 3. DETECCIÓN DE OPORTUNIDADES INSTITUCIONALES (7h - 19h UTC) ──
        if unprotected_risk_count < 4 and 7 <= hour <= 19:
            for sym, df in asset_dfs.items():
                if sym in active_positions or sym in pending_limits:
                    continue

                bar = map_bars[sym].get(current_dt)
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

                if atr <= 0 or ker_val < 0.25: continue

                is_bull = (c > ema50) and (ema50 > ema200) and fvg_bull
                is_bear = (c < ema50) and (ema50 < ema200) and fvg_bear
                if not (is_bull or is_bear): continue

                direction = "LONG" if is_bull else "SHORT"
                atr_sl_mult = 0.35

                if direction == "LONG":
                    fvg_low = float(df.iloc[idx-2]['high'])
                    entry = fvg_low
                    sl = float(min(df.iloc[idx-1]['low'], df.iloc[idx]['low'])) - (atr * atr_sl_mult)
                    risk = entry - sl
                    if risk <= 0 or (risk / entry) > 0.035: continue
                    be_target = entry + (risk * 1.2)
                    tp1 = entry + (risk * 1.5)
                    tp2 = entry + (risk * 2.5)
                    tp3 = entry + (risk * 3.5)
                else:
                    fvg_high = float(df.iloc[idx-2]['low'])
                    entry = fvg_high
                    sl = float(max(df.iloc[idx-1]['high'], df.iloc[idx]['high'])) + (atr * atr_sl_mult)
                    risk = sl - entry
                    if risk <= 0 or (risk / entry) > 0.035: continue
                    be_target = entry - (risk * 1.2)
                    tp1 = entry - (risk * 1.5)
                    tp2 = entry - (risk * 2.5)
                    tp3 = entry - (risk * 3.5)

                pending_limits[sym] = {
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

        # Tracking de Drawdown
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
    print("🚀 RESULTADO OFICIAL CON INTERÉS COMPUESTO DINÁMICO (90 DÍAS)")
    print("="*85)
    print(f"💰 Capital Inicial               : ${initial_capital:.2f} USD (Margen inicial $10)")
    print(f"💎 Capital Final con Compounding : ${equity:.2f} USD (Margen final ${equity*margin_pct:.2f})")
    print(f"💵 Ganancia Neta Total           : +${net_profit_usd:.2f} USD (+{roi_pct:.2f}%)")
    print(f"📊 Total de Trades Ejecutados    : {total_trades}")
    print(f"🏆 Trades Ganadores (Wins)       : {len(wins)} ({(len(wins)/total_trades)*100:.1f}%)")
    print(f"🛡️ Trades en Breakeven ($0)      : {len(be_trades)} ({(len(be_trades)/total_trades)*100:.1f}%)")
    print(f"📉 Drawdown Máximo del Portafolio: -{max_dd:.2f}%")
    print("="*85)

    print("\n📋 DESGLOSE POR ACTIVO (CON INTERÉS COMPUESTO):")
    print("-" * 85)
    by_asset = df_trades.groupby("symbol").agg(
        Trades=("pnl_usd", "count"),
        Wins=("pnl_usd", lambda x: (x > 0).sum()),
        Net_USD=("pnl_usd", "sum")
    ).reset_index()
    by_asset["Win_Rate"] = (by_asset["Wins"] / by_asset["Trades"] * 100).map("{:.1f}%".format)
    by_asset["Net_USD"] = by_asset["Net_USD"].map("+${:.2f}".format)
    by_asset.sort_values(by="Wins", ascending=False, inplace=True)
    print(by_asset.to_string(index=False))
    print("="*85 + "\n")

if __name__ == "__main__":
    run_compound_simulation()
