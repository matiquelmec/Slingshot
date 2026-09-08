import sys
import os
import glob
import json
import numpy as np
import pandas as pd
from typing import Dict, List, Any

# Parametros base FTMO
INITIAL_BALANCE = 100000.0
RISK_USD = 750.0 # 0.75%

TRADFI_SPECS = {
    "XAUUSD": {"contract_size": 100, "spread_usd": 0.25, "name": "Gold Spot", "long_only": True},
    "US100":  {"contract_size": 1,   "spread_usd": 1.50, "name": "Nasdaq 100", "long_only": False},
    "US500":  {"contract_size": 10,  "spread_usd": 0.40, "name": "S&P 500", "long_only": False},
    "US30":   {"contract_size": 1,   "spread_usd": 2.50, "name": "Dow Jones 30", "long_only": False},
    "GER40":  {"contract_size": 1,   "spread_usd": 1.50, "name": "DAX 40", "long_only": False},
    "EURUSD": {"contract_size": 100000, "spread_usd": 0.00010, "name": "EUR/USD", "long_only": False},
    "GBPUSD": {"contract_size": 100000, "spread_usd": 0.00012, "name": "GBP/USD", "long_only": False},
    "GBPJPY": {"contract_size": 100000, "spread_usd": 0.018, "name": "GBP/JPY", "long_only": False},
    "HGUSD":  {"contract_size": 25000,  "spread_usd": 0.0015, "name": "Copper", "long_only": False},
    "USOIL":  {"contract_size": 100, "spread_usd": 0.04, "name": "Crude Oil", "long_only": False},
    "XAGUSD": {"contract_size": 5000, "spread_usd": 0.02, "name": "Silver Spot", "long_only": False}
}

def simulate_asset(df: pd.DataFrame, sym: str, spec: dict, tf: str, min_confluence: int = 70, use_killzones: bool = True):
    # Ensure EMA50, EMA200, ATR
    df = df.copy()
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
        
    balance = INITIAL_BALANCE
    peak = INITIAL_BALANCE
    max_dd_usd = 0.0
    trades = []
    
    pos = None
    
    for i in range(50, len(df)):
        c = df.iloc[i]
        c_time = c["time"]
        c_high = float(c["high"])
        c_low = float(c["low"])
        c_close = float(c["close"])
        c_atr = float(c["atr"])
        ema50 = float(c["ema50"])
        ema200 = float(c["ema200"])
        
        # 1. Posicion abierta
        if pos is not None:
            is_long = pos["direction"] == "LONG"
            entry = pos["entry"]
            sl = pos["sl"]
            r_dist = pos["r_dist"]
            
            # Check SL
            sl_hit = (is_long and c_low <= sl) or (not is_long and c_high >= sl)
            if sl_hit:
                if pos["tp2_taken"]:
                    pnl = pos["harvested"] + ((RISK_USD * 1.0) * 0.20)
                    res = "WIN_TRAILING"
                elif pos["tp1_taken"]:
                    pnl = pos["harvested"]
                    res = "WIN_TP1_BE"
                elif pos["is_be"]:
                    pnl = 0.0
                    res = "FAST_BE"
                else:
                    pnl = -RISK_USD
                    res = "STOP_LOSS"
                    
                balance += pnl
                trades.append({"res": res, "pnl": pnl, "time": c_time})
                pos = None
                
                if balance > peak: peak = balance
                dd = peak - balance
                if dd > max_dd_usd: max_dd_usd = dd
                continue
                
            # Early Invalidation (-0.65R)
            current_r = (c_close - entry) / r_dist if is_long else (entry - c_close) / r_dist
            if not pos["is_be"] and not pos["tp1_taken"] and current_r <= -0.65:
                pnl = -RISK_USD * 0.65
                balance += pnl
                trades.append({"res": "EARLY_INV", "pnl": pnl, "time": c_time})
                pos = None
                if balance > peak: peak = balance
                dd = peak - balance
                if dd > max_dd_usd: max_dd_usd = dd
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
                    gain = (RISK_USD * 1.3) * 0.50
                    pos["harvested"] += gain
                    pos["is_be"] = True
                    pos["sl"] = entry
                    
            # TP2 (+2.5R, 30% cosecha)
            if pos["tp1_taken"] and not pos["tp2_taken"]:
                tp2_p = entry + (r_dist * 2.5) if is_long else entry - (r_dist * 2.5)
                if (is_long and c_high >= tp2_p) or (not is_long and c_low <= tp2_p):
                    pos["tp2_taken"] = True
                    gain = (RISK_USD * 2.5) * 0.30
                    pos["harvested"] += gain
                    pos["sl"] = entry + (r_dist * 1.0) if is_long else entry - (r_dist * 1.0)
                    
            # TP3 (+4.0R, 20% residual)
            if pos["tp2_taken"]:
                tp3_p = entry + (r_dist * 4.0) if is_long else entry - (r_dist * 4.0)
                if (is_long and c_high >= tp3_p) or (not is_long and c_low <= tp3_p):
                    gain = (RISK_USD * 4.0) * 0.20
                    pnl = pos["harvested"] + gain
                    balance += pnl
                    trades.append({"res": "FULL_TP3", "pnl": pnl, "time": c_time})
                    pos = None
                    if balance > peak: peak = balance
                    dd = peak - balance
                    if dd > max_dd_usd: max_dd_usd = dd
                    continue
                    
            if balance > peak: peak = balance
            dd = peak - balance
            if dd > max_dd_usd: max_dd_usd = dd
            continue
            
        # 2. Escaneo de nuevo setup
        h = c_time.hour
        if use_killzones and "XAU" not in sym:
            is_kz = (7 <= h <= 10) or (12 <= h <= 18)
            if not is_kz: continue
            
        is_bull = c_close > ema50 and ema50 > ema200
        is_bear = c_close < ema50 and ema50 < ema200
        
        if spec.get("long_only", False) and not is_bull:
            continue
            
        direction = "LONG" if is_bull else "SHORT" if is_bear else None
        if not direction:
            continue
            
        lookback = df.iloc[i-20:i]
        s_high = float(lookback["high"].max())
        s_low = float(lookback["low"].min())
        s_range = s_high - s_low
        if s_range <= (c_atr * 0.5):
            continue
            
        # Zona OTE 61.8%
        if direction == "LONG":
            entry_p = s_high - (s_range * 0.618)
            sl_p = s_low - (c_atr * 0.2)
        else:
            entry_p = s_low + (s_range * 0.618)
            sl_p = s_high + (c_atr * 0.2)
            
        r_dist = abs(entry_p - sl_p)
        if r_dist <= (spec["spread_usd"] * 2):
            continue
            
        # Evaluar si la vela actual penetro la zona OTE
        in_zone = (c_low <= entry_p <= c_high)
        if in_zone:
            pos = {
                "direction": direction,
                "entry": entry_p,
                "sl": sl_p,
                "r_dist": r_dist,
                "is_be": False,
                "tp1_taken": False,
                "tp2_taken": False,
                "harvested": 0.0
            }

    total = len(trades)
    if total == 0:
        return {"sym": sym, "tf": tf, "trades": 0, "pnl": 0.0, "roi": 0.0, "pf": 0.0, "wr": 0.0, "dd_pct": 0.0}
        
    wins = [t for t in trades if t["pnl"] > 0]
    bes = [t for t in trades if t["res"] == "FAST_BE"]
    losses = [t for t in trades if t["pnl"] < 0]
    
    g_profit = sum(t["pnl"] for t in wins)
    g_loss = abs(sum(t["pnl"] for t in losses))
    pf = (g_profit / g_loss) if g_loss > 0 else 99.0
    net_pnl = balance - INITIAL_BALANCE
    roi = (net_pnl / INITIAL_BALANCE) * 100.0
    eff_wr = (len(wins) + len(bes)) / total * 100.0
    dd_pct = (max_dd_usd / INITIAL_BALANCE) * 100.0
    
    return {
        "sym": sym,
        "tf": tf,
        "trades": total,
        "wins": len(wins),
        "be": len(bes),
        "losses": len(losses),
        "pnl": round(net_pnl, 2),
        "roi": round(roi, 2),
        "pf": round(pf, 2),
        "wr": round(eff_wr, 1),
        "dd_pct": round(dd_pct, 2)
    }

def main():
    print(f"{'ACTIVO':<8} | {'TF':<3} | {'TRADES':<6} | {'WINS':<5} | {'BE':<4} | {'LOSS':<5} | {'NET PNL':<11} | {'ROI %':<8} | {'PF':<5} | {'WR %':<6} | {'MAX DD %'}")
    print("-" * 95)
    
    data_dir = r"C:\Slingshot\engine\backtest\data"
    results = []
    
    for tf in ["1h", "15m"]:
        for sym, spec in TRADFI_SPECS.items():
            fpath = os.path.join(data_dir, f"{sym}_{tf}_audited.parquet")
            if not os.path.exists(fpath):
                continue
            df = pd.read_parquet(fpath)
            res = simulate_asset(df, sym, spec, tf)
            results.append(res)
            print(f"{res['sym']:<8} | {res['tf']:<3} | {res['trades']:<6} | {res['wins']:<5} | {res['be']:<4} | {res['losses']:<5} | ${res['pnl']:<10.2f} | {res['roi']:<+7.2f}% | {res['pf']:<5.2f} | {res['wr']:<5.1f}% | {res['dd_pct']:<5.2f}%")
        print("-" * 95)

if __name__ == "__main__":
    main()
