"""
scratch/execution_efficiency_audit.py
Audits the efficiency and return of 3 distinct execution engines on real 6mo historical data:
1. Engine A: Pure Limit OTE (Scanner Setup: Entry at Golden Pocket 61.8%, Zero Slippage, R:R 3.5:1)
2. Engine B: Pure Market Momentum (Entry after breakout confirmation, 0.25% Slippage, R:R 2.2:1)
3. Engine C: Apex Sniper Hybrid (Scanner identifies OTE zone + Tick Delta Confirmation, R:R 3.8:1 with Pyramiding at BE)
"""
import sys
import httpx
import numpy as np
import pandas as pd
from typing import Dict, List, Any

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

ASSETS = {
    "XAUUSD (Oro)": "GC=F",
    "US100 (Nasdaq)": "NQ=F",
    "BTCUSD (Bitcoin)": "BTC-USD",
    "RENDERUSDT": "RENDER-USD"
}

def fetch_data(ticker: str) -> pd.DataFrame:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=6mo&interval=1h"
    headers = {"User-Agent": "Mozilla/5.0"}
    with httpx.Client(timeout=15.0, verify=False) as client:
        res = client.get(url, headers=headers)
        res.raise_for_status()
        chart = res.json()["chart"]["result"][0]
        timestamps = chart["timestamp"]
        quotes = chart["indicators"]["quote"][0]
        df = pd.DataFrame({
            "timestamp": pd.to_datetime(timestamps, unit="s", utc=True),
            "open": quotes["open"],
            "high": quotes["high"],
            "low": quotes["low"],
            "close": quotes["close"],
            "volume": quotes.get("volume", [1000]*len(timestamps))
        }).dropna()
        
        df["tr"] = np.maximum(
            df["high"] - df["low"],
            np.maximum(abs(df["high"] - df["close"].shift(1)), abs(df["low"] - df["close"].shift(1)))
        )
        df["atr"] = df["tr"].rolling(14).mean().bfill()
        df["rvol"] = (df["volume"] / df["volume"].rolling(20).mean().bfill()).fillna(1.0)
        df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()
        df["ema200"] = df["close"].ewm(span=200, adjust=False).mean()
        return df

def audit_engine(df: pd.DataFrame, engine_type: str, initial_balance: float = 100000.0) -> Dict[str, Any]:
    balance = initial_balance
    peak = initial_balance
    max_dd_pct = 0.0
    trades = []
    active_pos = None
    
    for i in range(50, len(df)):
        c = df.iloc[i]
        c_open = c["open"]
        c_high = c["high"]
        c_low = c["low"]
        c_close = c["close"]
        c_atr = c["atr"]
        c_rvol = c["rvol"]
        ema50 = c["ema50"]
        ema200 = c["ema200"]
        
        if active_pos is not None:
            pos = active_pos
            is_long = pos["direction"] == "LONG"
            entry = pos["entry"]
            sl = pos["sl"]
            be = pos["be"]
            tp1 = pos["tp1"]
            tp_max = pos["tp_max"]
            risk_usd = pos["risk_usd"]
            
            sl_hit = (is_long and c_low <= sl) or (not is_long and c_high >= sl)
            if sl_hit:
                pnl = 0.0 if pos["is_be"] else -risk_usd
                balance += pnl
                trades.append({"result": "BE" if pos["is_be"] else "SL", "pnl": pnl})
                active_pos = None
            else:
                # Fast BE
                if not pos["is_be"]:
                    if (is_long and c_high >= be) or (not is_long and c_low <= be):
                        pos["is_be"] = True
                        pos["sl"] = entry
                        if pos["can_pyramid"] and not pos["pyramided"]:
                            pos["pyramided"] = True
                            pos["size_mult"] = 1.50 # Pyramiding +50%
                
                # TP1
                if not pos["tp1_hit"] and pos["tp1_ratio"] > 0:
                    if (is_long and c_high >= tp1) or (not is_long and c_low <= tp1):
                        pos["tp1_hit"] = True
                        gain1 = (risk_usd * pos["tp1_mult"]) * pos["tp1_ratio"]
                        balance += gain1
                        pos["pnl_acc"] += gain1
                        
                # TP Max
                if (is_long and c_high >= tp_max) or (not is_long and c_low <= tp_max):
                    rem_ratio = (1.0 - pos["tp1_ratio"]) if pos["tp1_ratio"] > 0 else 1.0
                    gain_max = (risk_usd * pos["tp_max_mult"] * pos["size_mult"]) * rem_ratio
                    balance += gain_max
                    trades.append({"result": "TP_MAX", "pnl": pos["pnl_acc"] + gain_max})
                    active_pos = None
                    
            if balance > peak: peak = balance
            dd = ((peak - balance) / peak) * 100.0 if peak > 0 else 0
            if dd > max_dd_pct: max_dd_pct = dd
            continue

        # Detección
        is_bull = c_close > ema50 and ema50 > ema200
        is_bear = c_close < ema50 and ema50 < ema200
        direction = "LONG" if is_bull else "SHORT" if is_bear else None
        if not direction: continue
        
        look = df.iloc[i-20:i]
        sh = look["high"].max()
        sl_w = look["low"].min()
        s_rng = sh - sl_w
        if s_rng <= c_atr * 0.5: continue
        
        ote = (sh - s_rng * 0.618) if direction == "LONG" else (sl_w + s_rng * 0.618)
        
        # -------------------------------------------------------------
        # CONFIGURACIÓN POR MOTOR DE EJECUCIÓN
        # -------------------------------------------------------------
        if engine_type == "A. Setup Límite OTE (Escáner)":
            # Entrada exacta en el nivel 61.8%, Zero Slippage
            if not (c_low <= ote <= c_high): continue
            entry_p = ote
            sl_p = (sl_w - c_atr * 0.2) if direction == "LONG" else (sh + c_atr * 0.2)
            r_dist = abs(entry_p - sl_p)
            if r_dist <= 0: continue
            
            risk_usd = 750.0 # 0.75%
            active_pos = {
                "direction": direction, "entry": entry_p, "sl": sl_p,
                "be": entry_p + (r_dist * 1.0 * (1 if direction == "LONG" else -1)),
                "tp1": entry_p + (r_dist * 1.3 * (1 if direction == "LONG" else -1)),
                "tp_max": entry_p + (r_dist * 3.5 * (1 if direction == "LONG" else -1)),
                "tp1_mult": 1.3, "tp_max_mult": 3.5, "tp1_ratio": 0.70,
                "risk_usd": risk_usd, "is_be": False, "tp1_hit": False,
                "can_pyramid": False, "pyramided": False, "size_mult": 1.0, "pnl_acc": 0.0
            }
            
        elif engine_type == "B. Market Momentum (Taker con Slippage)":
            # Entra a mercado cuando la vela confirma ruptura (Peor precio de entrada por slippage)
            slippage_atr = c_atr * 0.40
            entry_p = (c_close + slippage_atr) if direction == "LONG" else (c_close - slippage_atr)
            sl_p = (sl_w - c_atr * 0.2) if direction == "LONG" else (sh + c_atr * 0.2)
            r_dist = abs(entry_p - sl_p)
            if r_dist <= 0: continue
            
            risk_usd = 750.0
            active_pos = {
                "direction": direction, "entry": entry_p, "sl": sl_p,
                "be": entry_p + (r_dist * 1.0 * (1 if direction == "LONG" else -1)),
                "tp1": entry_p + (r_dist * 1.2 * (1 if direction == "LONG" else -1)),
                "tp_max": entry_p + (r_dist * 2.2 * (1 if direction == "LONG" else -1)), # R:R reducido por slippage
                "tp1_mult": 1.2, "tp_max_mult": 2.2, "tp1_ratio": 0.70,
                "risk_usd": risk_usd, "is_be": False, "tp1_hit": False,
                "can_pyramid": False, "pyramided": False, "size_mult": 1.0, "pnl_acc": 0.0
            }
            
        elif engine_type == "C. Apex Sniper Híbrido (Límite OTE + Pyramiding BE)":
            # Entrada límite óptima en OTE + Inyección de Pyramiding al llegar a BE
            if not (c_low <= ote <= c_high): continue
            entry_p = ote
            sl_p = (sl_w - c_atr * 0.2) if direction == "LONG" else (sh + c_atr * 0.2)
            r_dist = abs(entry_p - sl_p)
            if r_dist <= 0: continue
            
            risk_usd = 750.0
            active_pos = {
                "direction": direction, "entry": entry_p, "sl": sl_p,
                "be": entry_p + (r_dist * 1.0 * (1 if direction == "LONG" else -1)),
                "tp1": entry_p + (r_dist * 1.3 * (1 if direction == "LONG" else -1)),
                "tp_max": entry_p + (r_dist * 4.0 * (1 if direction == "LONG" else -1)),
                "tp1_mult": 1.3, "tp_max_mult": 4.0, "tp1_ratio": 0.50, # 50% TP1 + 50% Runner
                "risk_usd": risk_usd, "is_be": False, "tp1_hit": False,
                "can_pyramid": True, "pyramided": False, "size_mult": 1.0, "pnl_acc": 0.0
            }

    total = len(trades)
    wins = len([t for t in trades if t["result"] == "TP_MAX"])
    bes = len([t for t in trades if t["result"] == "BE"])
    losses = len([t for t in trades if t["result"] == "SL"])
    eff_wr = ((wins + bes) / total * 100.0) if total > 0 else 0.0
    tot_prof = sum(t["pnl"] for t in trades if t["pnl"] > 0)
    tot_loss = abs(sum(t["pnl"] for t in trades if t["pnl"] < 0))
    pf = (tot_prof / tot_loss) if tot_loss > 0 else 99.0
    roi = ((balance - initial_balance) / initial_balance) * 100.0
    calmar = (roi / max_dd_pct) if max_dd_pct > 0 else 99.0
    
    return {
        "engine": engine_type,
        "trades": total,
        "wins": wins,
        "bes": bes,
        "losses": losses,
        "eff_wr": eff_wr,
        "profit_factor": pf,
        "roi_pct": roi,
        "max_dd_pct": max_dd_pct,
        "calmar_ratio": calmar,
        "final_balance": balance
    }

def main():
    print("="*110)
    print("AUDITORIA DE EFICIENCIA: SETUPS LIMITE ESCANER vs MARKET MOMENTUM vs SNIPER HIBRIDO (6 MESES)")
    print("="*110)
    
    engines = [
        "A. Setup Límite OTE (Escáner)",
        "B. Market Momentum (Taker con Slippage)",
        "C. Apex Sniper Híbrido (Límite OTE + Pyramiding BE)"
    ]
    
    for sym_name, ticker in ASSETS.items():
        print(f"\n📈 ACTIVO: {sym_name}")
        df = fetch_data(ticker)
        print(f"{'Motor de Ejecución':<46} | {'Win Rate':<10} | {'Profit Factor':<14} | {'Max DD':<9} | {'Calmar':<7} | {'Retorno ($100k)'}")
        print("-" * 110)
        for eng in engines:
            res = audit_engine(df, eng)
            print(f"{res['engine']:<46} | {res['eff_wr']:<9.1f}% | {res['profit_factor']:<14.2f} | {res['max_dd_pct']:<8.2f}% | {res['calmar_ratio']:<6.1f} | +${res['final_balance']-100000:<13,.2f} ({res['roi_pct']:+.1f}%)")

if __name__ == "__main__":
    main()
