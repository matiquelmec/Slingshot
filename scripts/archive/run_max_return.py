"""
scratch/max_return_benchmark.py
Benchmarking Pure Maximum Return Strategies vs Risk-Adjusted FTMO Strategies.
Evaluates:
1. Apex_Hybrid_v19.1 (Current Baseline: 70% TP1 +1.3R, 30% TP3 +3.5R, Fast BE +1.0R, Flat 0.75%)
2. Full_Runner_No_Partial (100% position held to +3.5R, Fast BE +1.0R)
3. Pyramiding_Zero_Risk (Add +50% size once BE is activated, hold to +4.0R)
4. Compounding_Dynamic_Growth (Risk 1.0% of dynamic equity + 50% TP1 + 50% TP3)
5. Hyper_Growth_Sniper (Pyramiding + Dynamic Compounding)
"""
import sys
import httpx
import numpy as np
import pandas as pd
from typing import Dict, List, Any

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

TRADFI_TICKERS = {
    "XAUUSD (Oro)": "GC=F",
    "US100 (Nasdaq)": "NQ=F",
    "BTCUSD (Bitcoin)": "BTC-USD",
    "ETHUSD (Ethereum)": "ETH-USD"
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
        df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()
        df["ema200"] = df["close"].ewm(span=200, adjust=False).mean()
        return df

def simulate_max_return_variants(df: pd.DataFrame, variant_name: str, initial_balance: float = 100000.0) -> Dict[str, Any]:
    balance = initial_balance
    peak = initial_balance
    max_dd_pct = 0.0
    trades = []
    active_pos = None
    
    for i in range(50, len(df)):
        c = df.iloc[i]
        c_time = c["timestamp"]
        c_open = c["open"]
        c_high = c["high"]
        c_low = c["low"]
        c_close = c["close"]
        c_atr = c["atr"]
        ema50 = c["ema50"]
        ema200 = c["ema200"]
        
        # Gestión de Posición Activa
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
                # 1. Fast BE Check
                if not pos["is_be"]:
                    if (is_long and c_high >= be) or (not is_long and c_low <= be):
                        pos["is_be"] = True
                        pos["sl"] = entry # SL a Breakeven
                        
                        # Si es variante de Pyramiding: Añadir 50% más de tamaño a $0 riesgo
                        if "Pyramiding" in variant_name and not pos["pyramid_added"]:
                            pos["pyramid_added"] = True
                            pos["effective_size_mult"] = 1.50 # Aumenta retorno en ganadores un 50%
                
                # 2. TP1 Check (Parcial)
                if pos["has_tp1"] and not pos["tp1_hit"]:
                    if (is_long and c_high >= tp1) or (not is_long and c_low <= tp1):
                        pos["tp1_hit"] = True
                        gain1 = (risk_usd * 1.3) * pos["tp1_ratio"]
                        balance += gain1
                        pos["pnl_acc"] += gain1
                        
                # 3. TP Max Exit
                if (is_long and c_high >= tp_max) or (not is_long and c_low <= tp_max):
                    rem_ratio = pos["rem_ratio"] if pos["has_tp1"] else 1.0
                    gain_max = (risk_usd * pos["tp_max_r_mult"] * pos["effective_size_mult"]) * rem_ratio
                    balance += gain_max
                    trades.append({"result": "WIN_MAX", "pnl": pos["pnl_acc"] + gain_max})
                    active_pos = None
                    
            if balance > peak: peak = balance
            dd = ((peak - balance) / peak) * 100.0 if peak > 0 else 0
            if dd > max_dd_pct: max_dd_pct = dd
            continue

        # Entrada Cuantitativa Confluencia >= 65%
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
        if not (c_low <= ote <= c_high): continue
        
        entry_p = ote
        sl_p = (sl_w - c_atr * 0.2) if direction == "LONG" else (sh + c_atr * 0.2)
        r_dist = abs(entry_p - sl_p)
        if r_dist <= 0: continue
        
        # -------------------------------------------------------------
        # Configuración por Variante de Retorno
        # -------------------------------------------------------------
        if variant_name == "1. Apex Hybrid v19.1 (Actual)":
            risk_usd = 750.0 # Flat 0.75%
            has_tp1 = True; tp1_ratio = 0.70; rem_ratio = 0.30; tp_max_r = 3.5
            
        elif variant_name == "2. Full Runner (Sin Parciales)":
            risk_usd = 750.0 # Flat 0.75%
            has_tp1 = False; tp1_ratio = 0.0; rem_ratio = 1.0; tp_max_r = 3.5
            
        elif variant_name == "3. Pyramiding Cero Riesgo":
            risk_usd = 750.0 # Flat 0.75% (Añade +50% en BE)
            has_tp1 = True; tp1_ratio = 0.50; rem_ratio = 0.50; tp_max_r = 4.0
            
        elif variant_name == "4. Interés Compuesto Dinámico (1.0%)":
            risk_usd = balance * 0.010 # 1.0% reinvirtiendo ganancias
            has_tp1 = True; tp1_ratio = 0.60; rem_ratio = 0.40; tp_max_r = 3.8
            
        elif variant_name == "5. Hyper-Growth (Pyramiding + Compounding)":
            risk_usd = balance * 0.010 # 1.0% dinámico + Pyramiding
            has_tp1 = True; tp1_ratio = 0.50; rem_ratio = 0.50; tp_max_r = 4.5
            
        else:
            continue
            
        sign = 1.0 if direction == "LONG" else -1.0
        active_pos = {
            "direction": direction,
            "entry": entry_p,
            "sl": sl_p,
            "be": entry_p + (r_dist * 1.0 * sign),
            "tp1": entry_p + (r_dist * 1.3 * sign),
            "tp_max": entry_p + (r_dist * tp_max_r * sign),
            "tp_max_r_mult": tp_max_r,
            "has_tp1": has_tp1,
            "tp1_ratio": tp1_ratio,
            "rem_ratio": rem_ratio,
            "risk_usd": risk_usd,
            "is_be": False,
            "tp1_hit": False,
            "pyramid_added": False,
            "effective_size_mult": 1.0,
            "pnl_acc": 0.0
        }

    total = len(trades)
    wins = len([t for t in trades if t["result"] == "WIN_MAX"])
    bes = len([t for t in trades if t["result"] == "BE"])
    losses = len([t for t in trades if t["result"] == "SL"])
    eff_wr = ((wins + bes) / total * 100.0) if total > 0 else 0.0
    tot_prof = sum(t["pnl"] for t in trades if t["pnl"] > 0)
    tot_loss = abs(sum(t["pnl"] for t in trades if t["pnl"] < 0))
    pf = (tot_prof / tot_loss) if tot_loss > 0 else 99.0
    roi = ((balance - initial_balance) / initial_balance) * 100.0
    calmar = (roi / max_dd_pct) if max_dd_pct > 0 else 99.0
    
    return {
        "variant": variant_name,
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
    print("🔬 COMPARATIVA DE ESTRATEGIAS: MÁXIMO RETORNO BRUTO vs SUPERVIVENCIA FTMO (6 MESES REALES)")
    print("="*110)
    
    variants = [
        "1. Apex Hybrid v19.1 (Actual)",
        "2. Full Runner (Sin Parciales)",
        "3. Pyramiding Cero Riesgo",
        "4. Interés Compuesto Dinámico (1.0%)",
        "5. Hyper-Growth (Pyramiding + Compounding)"
    ]
    
    for sym_name, ticker in TRADFI_TICKERS.items():
        print(f"\n📈 ACTIVO: {sym_name}")
        df = fetch_data(ticker)
        print(f"{'Estrategia':<42} | {'Win Rate':<10} | {'Profit Factor':<14} | {'Max DD':<9} | {'Calmar':<7} | {'Retorno ($100k)'}")
        print("-" * 110)
        for v in variants:
            res = simulate_max_return_variants(df, v)
            print(f"{res['variant']:<42} | {res['eff_wr']:<9.1f}% | {res['profit_factor']:<14.2f} | {res['max_dd_pct']:<8.2f}% | {res['calmar_ratio']:<6.1f} | +${res['final_balance']-100000:<13,.2f} ({res['roi_pct']:+.1f}%)")

if __name__ == "__main__":
    main()
