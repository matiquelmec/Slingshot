import sys
import os
import json
import numpy as np
import pandas as pd
from typing import Dict, List, Any

# Parametros base FTMO
INITIAL_BALANCE = 100000.0
BASE_RISK_USD = 750.0 # 0.75%

# Comisiones reales FTMO por contrato (Round-Turn):
# Indices: $0 comision (costo solo en spread)
# Forex: $6 por lote estandar (100,000 unidades)
# Oro: $4 por lote (100 oz)
TRADFI_SPECS = {
    "XAUUSD": {"contract_size": 100, "spread_usd": 0.25, "commission_per_lot": 4.0, "name": "Gold Spot", "long_only": True, "tier": "A"},
    "US100":  {"contract_size": 1,   "spread_usd": 1.50, "commission_per_lot": 0.0, "name": "Nasdaq 100", "long_only": False, "tier": "A"},
    "GBPUSD": {"contract_size": 100000, "spread_usd": 0.00012, "commission_per_lot": 6.0, "name": "GBP/USD", "long_only": False, "tier": "A"},
    "US30":   {"contract_size": 1,   "spread_usd": 2.50, "commission_per_lot": 0.0, "name": "Dow Jones 30", "long_only": False, "tier": "A"},
    "GBPJPY": {"contract_size": 100000, "spread_usd": 0.018, "commission_per_lot": 6.0, "name": "GBP/JPY", "long_only": False, "tier": "B"},
    "XAGUSD": {"contract_size": 5000, "spread_usd": 0.02, "commission_per_lot": 4.0, "name": "Silver Spot", "long_only": False, "tier": "B"},
    "US500":  {"contract_size": 10,  "spread_usd": 0.40, "commission_per_lot": 0.0, "name": "S&P 500", "long_only": False, "tier": "B"},
    "USOIL":  {"contract_size": 100, "spread_usd": 0.04, "commission_per_lot": 0.0, "name": "Crude Oil", "long_only": False, "tier": "B"},
    "EURUSD": {"contract_size": 100000, "spread_usd": 0.00010, "commission_per_lot": 6.0, "name": "EUR/USD", "long_only": False, "tier": "C"},
    "HGUSD":  {"contract_size": 25000,  "spread_usd": 0.0015, "commission_per_lot": 0.0, "name": "Copper", "long_only": False, "tier": "C"},
    "GER40":  {"contract_size": 1,   "spread_usd": 1.50, "commission_per_lot": 0.0, "name": "DAX 40", "long_only": False, "tier": "C"}
}

def load_data(tf="15m", selected_symbols=None):
    data_dir = r"C:\Slingshot\engine\backtest\data"
    datasets = {}
    if selected_symbols is None:
        selected_symbols = list(TRADFI_SPECS.keys())
        
    for sym in selected_symbols:
        fpath = os.path.join(data_dir, f"{sym}_{tf}_audited.parquet")
        if os.path.exists(fpath):
            df = pd.read_parquet(fpath)
            if "time" in df.columns:
                df["time"] = pd.to_datetime(df["time"], utc=True)
            elif "timestamp" in df.columns:
                df["time"] = pd.to_datetime(df["timestamp"], utc=True)
            df = df.sort_values("time").reset_index(drop=True)
            if "ema50" not in df.columns:
                df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()
            if "ema200" not in df.columns:
                df["ema200"] = df["close"].ewm(span=200, adjust=False).mean()
            if "atr" not in df.columns:
                tr = np.maximum(df["high"] - df["low"], np.maximum(abs(df["high"] - df["close"].shift(1)), abs(df["low"] - df["close"].shift(1))))
                df["atr"] = tr.rolling(14).mean().bfill()
            datasets[sym] = df
    return datasets

def run_concurrent_portfolio(tf="15m", selected_symbols=None, max_slots=2, use_killzones=True):
    datasets = load_data(tf, selected_symbols)
    all_times = sorted(list(set(t for df in datasets.values() for t in df["time"])))
    time_indices = {sym: {t: i for i, t in enumerate(df["time"])} for sym, df in datasets.items()}
    
    balance = INITIAL_BALANCE
    peak = INITIAL_BALANCE
    max_dd_usd = 0.0
    daily_start_balance = INITIAL_BALANCE
    current_day = None
    daily_lockout = False
    daily_killswitch_hits = 0
    
    open_positions = []
    closed_trades = []
    
    for t_step in all_times:
        step_day = t_step.date()
        if step_day != current_day:
            current_day = step_day
            daily_start_balance = balance
            daily_lockout = False
            
        daily_loss = daily_start_balance - balance
        if daily_loss >= (daily_start_balance * 0.035):
            if not daily_lockout:
                daily_lockout = True
                daily_killswitch_hits += 1
                
        # 1. Gestionar posiciones abiertas
        active_remaining = []
        for pos in open_positions:
            sym = pos["symbol"]
            idx = time_indices[sym].get(t_step)
            if idx is None:
                active_remaining.append(pos)
                continue
                
            c = datasets[sym].iloc[idx]
            c_high = float(c["high"])
            c_low = float(c["low"])
            c_close = float(c["close"])
            
            is_long = pos["direction"] == "LONG"
            entry = pos["entry"]
            sl = pos["sl"]
            r_dist = pos["r_dist"]
            risk_usd = pos["risk_usd"]
            comm = pos["comm"]
            
            # SL hit
            sl_hit = (is_long and c_low <= sl) or (not is_long and c_high >= sl)
            if sl_hit:
                if pos["tp2_taken"]:
                    gain = (risk_usd * 1.0) * 0.20
                    pnl = pos["harvested"] + gain - comm
                    res = "WIN_TRAILING_+1.0R"
                elif pos["tp1_taken"]:
                    pnl = pos["harvested"] - comm
                    res = "WIN_TP1_BE"
                elif pos["is_be"]:
                    pnl = 0.0 - comm
                    res = "FAST_BE"
                else:
                    pnl = -risk_usd - comm
                    res = "STOP_LOSS"
                    
                balance += pnl
                pos["pnl"] = pnl
                pos["res"] = res
                pos["exit_time"] = t_step
                closed_trades.append(pos)
                continue
                
            # Early Invalidation (-0.65R)
            current_r = (c_close - entry) / r_dist if is_long else (entry - c_close) / r_dist
            if not pos["is_be"] and not pos["tp1_taken"] and current_r <= -0.65:
                pnl = (-risk_usd * 0.65) - comm
                balance += pnl
                pos["pnl"] = pnl
                pos["res"] = "EARLY_INV"
                pos["exit_time"] = t_step
                closed_trades.append(pos)
                continue
                
            # Fast BE (+1.0R)
            if not pos["is_be"]:
                be_hit = (is_long and c_high >= entry + r_dist) or (not is_long and c_low <= entry - r_dist)
                if be_hit:
                    pos["is_be"] = True
                    pos["sl"] = entry
                    
            # TP1 (+1.3R, 50% cosecha)
            if not pos["tp1_taken"]:
                tp1_p = entry + (r_dist * 1.3) if is_long else entry - (r_dist * 1.3)
                if (is_long and c_high >= tp1_p) or (not is_long and c_low <= tp1_p):
                    pos["tp1_taken"] = True
                    gain = (risk_usd * 1.3) * 0.50
                    pos["harvested"] += gain
                    pos["is_be"] = True
                    pos["sl"] = entry
                    
            # TP2 (+2.5R, 30% cosecha)
            if pos["tp1_taken"] and not pos["tp2_taken"]:
                tp2_p = entry + (r_dist * 2.5) if is_long else entry - (r_dist * 2.5)
                if (is_long and c_high >= tp2_p) or (not is_long and c_low <= tp2_p):
                    pos["tp2_taken"] = True
                    gain = (risk_usd * 2.5) * 0.30
                    pos["harvested"] += gain
                    pos["sl"] = entry + (r_dist * 1.0) if is_long else entry - (r_dist * 1.0)
                    
            # TP3 (+4.0R, 20% residual)
            if pos["tp2_taken"]:
                tp3_p = entry + (r_dist * 4.0) if is_long else entry - (r_dist * 4.0)
                if (is_long and c_high >= tp3_p) or (not is_long and c_low <= tp3_p):
                    gain = (risk_usd * 4.0) * 0.20
                    pnl = pos["harvested"] + gain - comm
                    balance += pnl
                    pos["pnl"] = pnl
                    pos["res"] = "FULL_TP3"
                    pos["exit_time"] = t_step
                    closed_trades.append(pos)
                    continue
                    
            active_remaining.append(pos)
        open_positions = active_remaining
        
        # Track drawdown
        cur_eq = balance + sum(p["harvested"] for p in open_positions)
        if cur_eq > peak: peak = cur_eq
        dd = peak - cur_eq
        if dd > max_dd_usd: max_dd_usd = dd
        
        # 2. Apertura de nuevas posiciones
        if daily_lockout:
            continue
            
        unprotected = sum(1 for p in open_positions if not p["is_be"])
        if unprotected >= max_slots:
            continue
            
        # Assets currently held
        held_syms = set(p["symbol"] for p in open_positions)
        
        # Scan candidates
        for sym, df in datasets.items():
            if sym in held_syms:
                continue
            if unprotected >= max_slots:
                break
                
            idx = time_indices[sym].get(t_step)
            if idx is None or idx < 50:
                continue
                
            c = df.iloc[idx]
            c_high = float(c["high"])
            c_low = float(c["low"])
            c_close = float(c["close"])
            c_atr = float(c["atr"])
            ema50 = float(c["ema50"])
            ema200 = float(c["ema200"])
            
            h = t_step.hour
            if use_killzones and "XAU" not in sym:
                is_kz = (7 <= h <= 10) or (12 <= h <= 18)
                if not is_kz: continue
                
            is_bull = c_close > ema50 and ema50 > ema200
            is_bear = c_close < ema50 and ema50 < ema200
            
            spec = TRADFI_SPECS[sym]
            if spec.get("long_only", False) and not is_bull:
                continue
                
            direction = "LONG" if is_bull else "SHORT" if is_bear else None
            if not direction:
                continue
                
            lookback = df.iloc[idx-20:idx]
            s_high = float(lookback["high"].max())
            s_low = float(lookback["low"].min())
            s_range = s_high - s_low
            if s_range <= (c_atr * 0.5):
                continue
                
            if direction == "LONG":
                entry_p = s_high - (s_range * 0.618)
                sl_p = s_low - (c_atr * 0.2)
            else:
                entry_p = s_low + (s_range * 0.618)
                sl_p = s_high + (c_atr * 0.2)
                
            r_dist = abs(entry_p - sl_p)
            if r_dist <= (spec["spread_usd"] * 2):
                continue
                
            in_zone = (c_low <= entry_p <= c_high)
            if in_zone:
                lots = BASE_RISK_USD / (r_dist * spec["contract_size"])
                comm = lots * spec["commission_per_lot"]
                
                pos = {
                    "symbol": sym,
                    "direction": direction,
                    "entry": entry_p,
                    "sl": sl_p,
                    "r_dist": r_dist,
                    "risk_usd": BASE_RISK_USD,
                    "comm": comm,
                    "is_be": False,
                    "tp1_taken": False,
                    "tp2_taken": False,
                    "harvested": 0.0,
                    "entry_time": t_step
                }
                open_positions.append(pos)
                held_syms.add(sym)
                unprotected += 1
                
    # Summary
    total = len(closed_trades)
    wins = [t for t in closed_trades if t["pnl"] > 0]
    bes = [t for t in closed_trades if t["res"] == "FAST_BE"]
    losses = [t for t in closed_trades if t["pnl"] < 0]
    
    g_profit = sum(t["pnl"] for t in wins)
    g_loss = abs(sum(t["pnl"] for t in losses))
    pf = (g_profit / g_loss) if g_loss > 0 else 99.0
    net_pnl = balance - INITIAL_BALANCE
    roi = (net_pnl / INITIAL_BALANCE) * 100.0
    eff_wr = (len(wins) + len(bes)) / total * 100.0 if total > 0 else 0.0
    dd_pct = (max_dd_usd / peak) * 100.0 if peak > 0 else 0.0
    
    return {
        "tf": tf,
        "symbols": selected_symbols,
        "trades": total,
        "wins": len(wins),
        "be": len(bes),
        "losses": len(losses),
        "balance": round(balance, 2),
        "net_pnl": round(net_pnl, 2),
        "roi": round(roi, 2),
        "pf": round(pf, 2),
        "wr": round(eff_wr, 1),
        "max_dd_pct": round(dd_pct, 2),
        "killswitch_hits": daily_killswitch_hits,
        "ftmo_passed": roi >= 10.0 and dd_pct < 10.0
    }

def main():
    print("=" * 80)
    print("SIMULACION DE CARTERAS CONCURRENTES FTMO (SLOT FORTRESS = 2)")
    print("=" * 80)
    
    configs = [
        ("15m - Todos los 11 Activos", "15m", list(TRADFI_SPECS.keys())),
        ("15m - Solo Tier A (XAUUSD, US100, GBPUSD, US30)", "15m", ["XAUUSD", "US100", "GBPUSD", "US30"]),
        ("15m - Solo Top 3 (XAUUSD, US100, GBPUSD)", "15m", ["XAUUSD", "US100", "GBPUSD"]),
        ("1h  - Todos los 11 Activos", "1h", list(TRADFI_SPECS.keys())),
        ("1h  - Top 4 (EURUSD, GBPJPY, GBPUSD, US100)", "1h", ["EURUSD", "GBPJPY", "GBPUSD", "US100"]),
        ("1h  - Core Duo (US100, XAUUSD)", "1h", ["US100", "XAUUSD"])
    ]
    
    for label, tf, syms in configs:
        res = run_concurrent_portfolio(tf, syms, max_slots=2, use_killzones=True)
        print(f"\n[{label}]")
        print(f"  Balance Final:   ${res['balance']:,.2f} USD ({res['roi']:+.2f}%)")
        print(f"  Profit Factor:   {res['pf']:.2f} | Win Rate Efectivo: {res['wr']:.1f}%")
        print(f"  Total Trades:    {res['trades']} (Wins: {res['wins']} | BE: {res['be']} | Loss: {res['losses']})")
        print(f"  Max Drawdown:    -{res['max_dd_pct']:.2f}% | Killswitch hits: {res['killswitch_hits']}")
        print(f"  Estatus FTMO:    {'*** APROBADO CON EXITO ***' if res['ftmo_passed'] else 'No superado / En curso'}")
        print("-" * 60)

if __name__ == "__main__":
    main()
