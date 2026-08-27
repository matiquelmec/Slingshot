"""
scratch/threshold_optimization_study.py
Parametric optimization of confluence threshold from 50% to 85% on real 6-month data.
Analyzes Trade Frequency, Win Rate, Profit Factor, Max Drawdown, and FTMO Pass Probability.
"""
import httpx
import numpy as np
import pandas as pd
from typing import Dict, List, Any

TRADFI_TICKERS = {
    "XAUUSD": "GC=F",
    "US100":  "NQ=F",
    "BTCUSD": "BTC-USD",
    "ETHUSD": "ETH-USD"
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

def simulate_with_threshold(df: pd.DataFrame, threshold: int, initial_balance: float = 100000.0, risk_pct: float = 0.0075) -> Dict[str, Any]:
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
        
        if active_pos is not None:
            pos = active_pos
            is_long = pos["direction"] == "LONG"
            entry = pos["entry"]
            sl = pos["sl"]
            be = pos["be"]
            tp1 = pos["tp1"]
            tp3 = pos["tp3"]
            risk_usd = pos["risk_usd"]
            
            sl_hit = (is_long and c_low <= sl) or (not is_long and c_high >= sl)
            if sl_hit:
                pnl = 0.0 if pos["is_be"] else -risk_usd
                balance += pnl
                trades.append({"result": "BE" if pos["is_be"] else "SL", "pnl": pnl})
                active_pos = None
            else:
                if not pos["is_be"]:
                    if (is_long and c_high >= be) or (not is_long and c_low <= be):
                        pos["is_be"] = True
                        pos["sl"] = entry
                if not pos["tp1"]:
                    if (is_long and c_high >= tp1) or (not is_long and c_low <= tp1):
                        pos["tp1"] = True
                        gain = (risk_usd * 1.3) * 0.70
                        balance += gain
                        pos["pnl_acc"] += gain
                if (is_long and c_high >= tp3) or (not is_long and c_low <= tp3):
                    rem_gain = (risk_usd * 3.5) * (0.30 if pos["tp1"] else 1.0)
                    balance += rem_gain
                    trades.append({"result": "TP", "pnl": pos["pnl_acc"] + rem_gain})
                    active_pos = None
            
            if balance > peak: peak = balance
            dd = ((peak - balance) / peak) * 100.0 if peak > 0 else 0
            if dd > max_dd_pct: max_dd_pct = dd
            continue

        # Evaluación de Confluencia
        is_bull = c_close > ema50 and ema50 > ema200
        is_bear = c_close < ema50 and ema50 < ema200
        direction = "LONG" if is_bull else "SHORT" if is_bear else None
        if not direction: continue
        
        # Lookback 20
        look = df.iloc[i-20:i]
        sh = look["high"].max()
        sl_w = look["low"].min()
        s_rng = sh - sl_w
        if s_rng <= c_atr * 0.5: continue
        
        score = 50
        if (direction == "LONG" and c_close > ema200) or (direction == "SHORT" and c_close < ema200):
            score += 15
        
        hour = c_time.hour
        is_killzone = (7 <= hour <= 11) or (13 <= hour <= 17)
        if is_killzone:
            score += 10
            
        ote = (sh - s_rng * 0.618) if direction == "LONG" else (sl_w + s_rng * 0.618)
        if c_low <= ote <= c_high:
            score += 15
            
        # Filtro de Umbral
        if score < threshold:
            continue
            
        entry_p = ote
        sl_p = (sl_w - c_atr * 0.2) if direction == "LONG" else (sh + c_atr * 0.2)
        r_dist = abs(entry_p - sl_p)
        if r_dist <= 0: continue
        
        risk_usd = balance * risk_pct
        active_pos = {
            "direction": direction,
            "entry": entry_p,
            "sl": sl_p,
            "be": entry_p + (r_dist * 1.0 if direction == "LONG" else -r_dist * 1.0),
            "tp1": entry_p + (r_dist * 1.3 if direction == "LONG" else -r_dist * 1.3),
            "tp3": entry_p + (r_dist * 3.5 if direction == "LONG" else -r_dist * 3.5),
            "risk_usd": risk_usd,
            "is_be": False,
            "tp1": False,
            "pnl_acc": 0.0
        }

    total = len(trades)
    wins = len([t for t in trades if t["result"] == "TP"])
    bes = len([t for t in trades if t["result"] == "BE"])
    losses = len([t for t in trades if t["result"] == "SL"])
    eff_wr = ((wins + bes) / total * 100.0) if total > 0 else 0.0
    tot_prof = sum(t["pnl"] for t in trades if t["pnl"] > 0)
    tot_loss = abs(sum(t["pnl"] for t in trades if t["pnl"] < 0))
    pf = (tot_prof / tot_loss) if tot_loss > 0 else 99.0
    roi = ((balance - initial_balance) / initial_balance) * 100.0
    
    return {
        "threshold": threshold,
        "trades": total,
        "wins": wins,
        "bes": bes,
        "losses": losses,
        "eff_wr": eff_wr,
        "profit_factor": pf,
        "roi_pct": roi,
        "max_dd_pct": max_dd_pct,
        "final_balance": balance
    }

def main():
    import sys
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    print("="*85)
    print("ESTUDIO PARAMETRICO DE CONFLUENCIA (50% a 85%) - IMPACTO EN FTMO & RETORNO")
    print("="*85)
    
    thresholds = [50, 60, 65, 70, 75, 80]
    
    for symbol, ticker in TRADFI_TICKERS.items():
        print(f"\n📊 Activo: {symbol} ({ticker})")
        df = fetch_data(ticker)
        print(f"{'Umbral':<8} | {'Trades':<8} | {'Win Rate Ef.':<13} | {'Profit Factor':<14} | {'Max DD':<9} | {'Retorno ($100k)':<16} | {'Pase FTMO'}")
        print("-" * 88)
        for th in thresholds:
            res = simulate_with_threshold(df, th)
            pass_status = "✅ APROBADO (+10%)" if res["roi_pct"] >= 10.0 else ("⚠️ REPROBADO (DD > 8%)" if res["max_dd_pct"] > 8.0 else "⏳ EN CURSO")
            print(f"{res['threshold']}%{'':<4} | {res['trades']:<8} | {res['eff_wr']:<12.1f}% | {res['profit_factor']:<14.2f} | {res['max_dd_pct']:<8.2f}% | +${res['final_balance']-100000:<14,.2f} ({res['roi_pct']:+.1f}%) | {pass_status}")

if __name__ == "__main__":
    main()
