"""
scratch/threshold_60_vs_65_deep_audit.py
Backtest comparativo exacto de 6 meses (datos reales) entre:
- Umbral 60% (Permisivo: Captura señales como SOLUSDT 63%)
- Umbral 65% (Recomendado actual)
- Umbral 70% (Conservador)

Evalúa métricas clave:
1. Total de Trades
2. Win Rate Efectivo (con Fast BE)
3. Profit Factor (PF)
4. Max Drawdown Diario (%)
5. Retorno Neto ($100k)
6. Calmar Ratio (Retorno / Max DD)
7. Tasa de Falsos Positivos (Trades que tocaron SL directo sin llegar a BE)
"""
import sys
import httpx
import numpy as np
import pandas as pd
from typing import Dict, List, Any

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

ASSETS = {
    "SOLUSDT (Solana)": "SOL-USD",
    "BTCUSD (Bitcoin)": "BTC-USD",
    "ETHUSD (Ethereum)": "ETH-USD",
    "XAUUSD (Oro)": "GC=F",
    "US100 (Nasdaq)": "NQ=F"
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

def run_backtest_for_threshold(df: pd.DataFrame, min_confluence: int, initial_balance: float = 100000.0) -> Dict[str, Any]:
    balance = initial_balance
    peak = initial_balance
    max_dd_pct = 0.0
    daily_starting_bal = initial_balance
    current_day = None
    max_daily_dd = 0.0
    
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
        c_rvol = c["rvol"]
        ema50 = c["ema50"]
        ema200 = c["ema200"]
        
        # Tracking diario
        day_str = c_time.strftime("%Y-%m-%d")
        if current_day != day_str:
            current_day = day_str
            daily_starting_bal = balance
            
        daily_dd = (daily_starting_bal - balance) / daily_starting_bal * 100.0 if daily_starting_bal > 0 else 0
        if daily_dd > max_daily_dd: max_daily_dd = daily_dd
        
        # Gestión de Posición
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
                trades.append({
                    "result": "BE" if pos["is_be"] else "SL",
                    "pnl": pnl,
                    "is_direct_sl": not pos["is_be"]
                })
                active_pos = None
            else:
                # Fast BE (+1.0R)
                if not pos["is_be"]:
                    if (is_long and c_high >= be) or (not is_long and c_low <= be):
                        pos["is_be"] = True
                        pos["sl"] = entry # Breakeven
                        
                # TP1 (+1.3R / 70%)
                if not pos["tp1_hit"]:
                    if (is_long and c_high >= tp1) or (not is_long and c_low <= tp1):
                        pos["tp1_hit"] = True
                        gain1 = (risk_usd * 1.3) * 0.70
                        balance += gain1
                        pos["pnl_acc"] += gain1
                        
                # TP3 (+3.5R / 30% Runner)
                if (is_long and c_high >= tp3) or (not is_long and c_low <= tp3):
                    rem_ratio = 0.30 if pos["tp1_hit"] else 1.0
                    gain3 = (risk_usd * 3.5) * rem_ratio
                    balance += gain3
                    trades.append({"result": "TP3", "pnl": pos["pnl_acc"] + gain3, "is_direct_sl": False})
                    active_pos = None
                    
            if balance > peak: peak = balance
            dd = ((peak - balance) / peak) * 100.0 if peak > 0 else 0
            if dd > max_dd_pct: max_dd_pct = dd
            continue

        # Reglas SMC + OTE
        is_bull = c_close > ema50 and ema50 > ema200
        is_bear = c_close < ema50 and ema50 < ema200
        direction = "LONG" if is_bull else "SHORT" if is_bear else None
        if not direction: continue
        
        look = df.iloc[i-20:i]
        sh = look["high"].max()
        sl_w = look["low"].min()
        s_rng = sh - sl_w
        if s_rng <= c_atr * 0.5: continue
        
        hour = c_time.hour
        is_killzone = (7 <= hour <= 11) or (13 <= hour <= 17)
        
        score = 50
        if (direction == "LONG" and c_close > ema200) or (direction == "SHORT" and c_close < ema200): score += 15
        if is_killzone: score += 10
        if c_rvol >= 1.3: score += 10
        ote = (sh - s_rng * 0.618) if direction == "LONG" else (sl_w + s_rng * 0.618)
        if c_low <= ote <= c_high: score += 15
        
        if score < min_confluence: continue
        
        entry_p = ote
        sl_p = (sl_w - c_atr * 0.2) if direction == "LONG" else (sh + c_atr * 0.2)
        r_dist = abs(entry_p - sl_p)
        if r_dist <= 0: continue
        
        risk_usd = 750.0 # 0.75%
        sign = 1.0 if direction == "LONG" else -1.0
        
        active_pos = {
            "direction": direction,
            "entry": entry_p,
            "sl": sl_p,
            "be": entry_p + (r_dist * 1.0 * sign),
            "tp1": entry_p + (r_dist * 1.3 * sign),
            "tp3": entry_p + (r_dist * 3.5 * sign),
            "risk_usd": risk_usd,
            "is_be": False,
            "tp1_hit": False,
            "pnl_acc": 0.0
        }

    total = len(trades)
    wins = len([t for t in trades if t["result"] == "TP3"])
    bes = len([t for t in trades if t["result"] == "BE"])
    direct_losses = len([t for t in trades if t["result"] == "SL"])
    eff_wr = ((wins + bes) / total * 100.0) if total > 0 else 0.0
    tot_prof = sum(t["pnl"] for t in trades if t["pnl"] > 0)
    tot_loss = abs(sum(t["pnl"] for t in trades if t["pnl"] < 0))
    pf = (tot_prof / tot_loss) if tot_loss > 0 else 99.0
    roi = ((balance - initial_balance) / initial_balance) * 100.0
    calmar = (roi / max_dd_pct) if max_dd_pct > 0 else 99.0
    
    return {
        "threshold": f"{min_confluence}%",
        "trades": total,
        "direct_losses": direct_losses,
        "eff_wr": eff_wr,
        "profit_factor": pf,
        "max_daily_dd": max_daily_dd,
        "max_dd_pct": max_dd_pct,
        "calmar": calmar,
        "net_profit": balance - initial_balance,
        "roi_pct": roi
    }

def main():
    print("="*115)
    print("🔬 AUDITORÍA CUANTITATIVA Y BACKTEST DE 6 MESES: UMBRAL 60% vs 65% vs 70%")
    print("="*115)
    
    thresholds = [60, 65, 70]
    
    for sym_name, ticker in ASSETS.items():
        print(f"\n📈 ACTIVO: {sym_name}")
        df = fetch_data(ticker)
        print(f"{'Umbral':<10} | {'Trades':<8} | {'SL Directos':<12} | {'Win Rate Ef.':<13} | {'Profit Factor':<14} | {'Max DD':<9} | {'Retorno ($100k)'}")
        print("-" * 115)
        for th in thresholds:
            res = run_backtest_for_threshold(df, th)
            print(f"{res['threshold']:<10} | {res['trades']:<8} | {res['direct_losses']:<12} | {res['eff_wr']:<12.1f}% | {res['profit_factor']:<14.2f} | {res['max_dd_pct']:<8.2f}% | +${res['net_profit']:<12,.2f} ({res['roi_pct']:+.1f}%)")

if __name__ == "__main__":
    main()
