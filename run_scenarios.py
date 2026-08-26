"""
scratch/advanced_scenario_matrix.py
Exhaustive Multi-Scenario Matrix Analysis:
- Scenario A: Baseline v18 (Confluence 65%, Fast BE +1.0R, TP1 +1.3R 70%, TP3 +3.5R 30%, Risk 0.75% flat)
- Scenario B: High-Beta Dynamic TP (Fast BE +0.85R, TP1 +1.5R 60%, TP2 +2.5R 20%, TP3 +4.5R 20% Runner)
- Scenario C: Regime-Adaptive (Trend: 4.5R runner | Chop: Quick 1.2R scalp, Risk 0.5%)
- Scenario D: Institutional Killzones & RVOL >= 1.4x (Zero trades outside London/NY Open)
- Scenario E: Asymmetric Alpha Kelly (Tiered Risk: Elite 1.0% | High 0.65% | Tactical 0.40% + Half-Size on DD > 1.5%)
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
        df["rvol"] = (df["volume"] / df["volume"].rolling(20).mean().bfill()).fillna(1.0)
        df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()
        df["ema200"] = df["close"].ewm(span=200, adjust=False).mean()
        # ADX Approximation / Trend Strength
        df["up_move"] = df["high"] - df["high"].shift(1)
        df["down_move"] = df["low"].shift(1) - df["low"]
        df["plus_dm"] = np.where((df["up_move"] > df["down_move"]) & (df["up_move"] > 0), df["up_move"], 0.0)
        df["minus_dm"] = np.where((df["down_move"] > df["up_move"]) & (df["down_move"] > 0), df["down_move"], 0.0)
        df["plus_di"] = 100 * (df["plus_dm"].rolling(14).mean() / df["atr"])
        df["minus_di"] = 100 * (df["minus_dm"].rolling(14).mean() / df["atr"])
        df["dx"] = 100 * np.abs(df["plus_di"] - df["minus_di"]) / (df["plus_di"] + df["minus_di"] + 1e-6)
        df["adx"] = df["dx"].rolling(14).mean().bfill()
        return df

def run_scenario(df: pd.DataFrame, scenario_name: str, initial_balance: float = 100000.0) -> Dict[str, Any]:
    balance = initial_balance
    peak = initial_balance
    max_dd_pct = 0.0
    daily_starting_bal = initial_balance
    current_day = None
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
        c_adx = c["adx"]
        ema50 = c["ema50"]
        ema200 = c["ema200"]
        
        # Tracking diario de drawdown
        day_str = c_time.strftime("%Y-%m-%d")
        if current_day != day_str:
            current_day = day_str
            daily_starting_bal = balance
            
        daily_dd = (daily_starting_bal - balance) / daily_starting_bal * 100.0 if daily_starting_bal > 0 else 0
        
        # Gestión de Posición Activa
        if active_pos is not None:
            pos = active_pos
            is_long = pos["direction"] == "LONG"
            entry = pos["entry"]
            sl = pos["sl"]
            be = pos["be"]
            tp1 = pos["tp1"]
            tp2 = pos["tp2"]
            tp3 = pos["tp3"]
            risk_usd = pos["risk_usd"]
            tp1_ratio = pos["tp1_ratio"]
            tp2_ratio = pos["tp2_ratio"]
            tp3_ratio = pos["tp3_ratio"]
            
            sl_hit = (is_long and c_low <= sl) or (not is_long and c_high >= sl)
            if sl_hit:
                pnl = 0.0 if pos["is_be"] else -risk_usd
                balance += pnl
                trades.append({"result": "BE" if pos["is_be"] else "SL", "pnl": pnl, "time": c_time})
                active_pos = None
            else:
                # Fast BE Check
                if not pos["is_be"]:
                    if (is_long and c_high >= be) or (not is_long and c_low <= be):
                        pos["is_be"] = True
                        pos["sl"] = entry # Breakeven
                        
                # TP1 Check
                if not pos["tp1_hit"]:
                    if (is_long and c_high >= tp1) or (not is_long and c_low <= tp1):
                        pos["tp1_hit"] = True
                        gain1 = (risk_usd * pos["tp1_r_mult"]) * tp1_ratio
                        balance += gain1
                        pos["pnl_acc"] += gain1
                        
                # TP2 Check
                if not pos["tp2_hit"] and tp2 is not None:
                    if (is_long and c_high >= tp2) or (not is_long and c_low <= tp2):
                        pos["tp2_hit"] = True
                        gain2 = (risk_usd * pos["tp2_r_mult"]) * tp2_ratio
                        balance += gain2
                        pos["pnl_acc"] += gain2
                        
                # TP3 Check (Runner / Max Exit)
                if (is_long and c_high >= tp3) or (not is_long and c_low <= tp3):
                    rem_ratio = tp3_ratio if (pos["tp1_hit"] or pos["tp2_hit"]) else 1.0
                    gain3 = (risk_usd * pos["tp3_r_mult"]) * rem_ratio
                    balance += gain3
                    trades.append({"result": "TP_RUNNER", "pnl": pos["pnl_acc"] + gain3, "time": c_time})
                    active_pos = None
                    
            if balance > peak: peak = balance
            dd = ((peak - balance) / peak) * 100.0 if peak > 0 else 0
            if dd > max_dd_pct: max_dd_pct = dd
            continue

        # Reglas de Entrada según Escenario
        is_bull = c_close > ema50 and ema50 > ema200
        is_bear = c_close < ema50 and ema50 < ema200
        direction = "LONG" if is_bull else "SHORT" if is_bear else None
        if not direction: continue
        
        # Swings OTE Lookback 20
        look = df.iloc[i-20:i]
        sh = look["high"].max()
        sl_w = look["low"].min()
        s_rng = sh - sl_w
        if s_rng <= c_atr * 0.5: continue
        
        hour = c_time.hour
        is_killzone = (7 <= hour <= 11) or (13 <= hour <= 17)
        
        # Confluence Score Base
        score = 50
        if (direction == "LONG" and c_close > ema200) or (direction == "SHORT" and c_close < ema200): score += 15
        if is_killzone: score += 10
        if c_rvol >= 1.4: score += 10
        ote = (sh - s_rng * 0.618) if direction == "LONG" else (sl_w + s_rng * 0.618)
        if c_low <= ote <= c_high: score += 15
        
        # -------------------------------------------------------------
        # Configuración Paramétrica por Escenario
        # -------------------------------------------------------------
        if scenario_name == "A_Baseline_65":
            if score < 65: continue
            risk_pct = 0.0075 # 0.75%
            be_dist = 1.0; tp1_dist = 1.3; tp2_dist = None; tp3_dist = 3.5
            tp1_ratio = 0.70; tp2_ratio = 0.00; tp3_ratio = 0.30
            
        elif scenario_name == "B_HighBeta_Runner":
            if score < 65: continue
            risk_pct = 0.0075
            be_dist = 0.85; tp1_dist = 1.5; tp2_dist = 2.5; tp3_dist = 4.5
            tp1_ratio = 0.50; tp2_ratio = 0.25; tp3_ratio = 0.25
            
        elif scenario_name == "C_Regime_Adaptive":
            if score < 60: continue
            is_trending = c_adx > 25
            if is_trending:
                risk_pct = 0.0085 # 0.85% en tendencia
                be_dist = 1.0; tp1_dist = 1.5; tp2_dist = 2.5; tp3_dist = 5.0
                tp1_ratio = 0.50; tp2_ratio = 0.25; tp3_ratio = 0.25
            else: # Rango / Choppy
                risk_pct = 0.0040 # 0.40% en rango
                be_dist = 0.75; tp1_dist = 1.2; tp2_dist = None; tp3_dist = 2.0
                tp1_ratio = 0.80; tp2_ratio = 0.00; tp3_ratio = 0.20
                
        elif scenario_name == "D_Killzone_Strict":
            # Exige estar estrictamente en Killzone Londres o NY + RVOL >= 1.3x
            if not is_killzone or c_rvol < 1.2 or score < 65: continue
            risk_pct = 0.0075
            be_dist = 0.90; tp1_dist = 1.4; tp2_dist = 2.2; tp3_dist = 3.8
            tp1_ratio = 0.60; tp2_ratio = 0.20; tp3_ratio = 0.20
            
        elif scenario_name == "E_Asymmetric_Alpha_Kelly":
            if score < 60: continue
            # Dimensionamiento Asimétrico de Kelly Cuantitativo
            if score >= 80:
                base_risk = 0.0100 # 1.00% (Alpha Máximo)
            elif score >= 70:
                base_risk = 0.0075 # 0.75% (Estándar)
            else:
                base_risk = 0.0045 # 0.45% (Táctico)
                
            # Freno de Seguridad en Drawdown
            if daily_dd >= 1.5:
                base_risk *= 0.50 # Reduce riesgo al 50% si el día viene en negativo
                
            risk_pct = base_risk
            be_dist = 0.90; tp1_dist = 1.4; tp2_dist = 2.4; tp3_dist = 4.2
            tp1_ratio = 0.60; tp2_ratio = 0.20; tp3_ratio = 0.20
            
        else:
            continue

        entry_p = ote
        sl_p = (sl_w - c_atr * 0.2) if direction == "LONG" else (sh + c_atr * 0.2)
        r_dist = abs(entry_p - sl_p)
        if r_dist <= 0: continue
        
        risk_usd = balance * risk_pct
        sign = 1.0 if direction == "LONG" else -1.0
        
        active_pos = {
            "direction": direction,
            "entry": entry_p,
            "sl": sl_p,
            "be": entry_p + (r_dist * be_dist * sign),
            "tp1": entry_p + (r_dist * tp1_dist * sign),
            "tp2": (entry_p + (r_dist * tp2_dist * sign)) if tp2_dist else None,
            "tp3": entry_p + (r_dist * tp3_dist * sign),
            "tp1_r_mult": tp1_dist,
            "tp2_r_mult": tp2_dist or 0.0,
            "tp3_r_mult": tp3_dist,
            "tp1_ratio": tp1_ratio,
            "tp2_ratio": tp2_ratio,
            "tp3_ratio": tp3_ratio,
            "risk_usd": risk_usd,
            "is_be": False,
            "tp1_hit": False,
            "tp2_hit": False,
            "pnl_acc": 0.0
        }

    total = len(trades)
    wins = len([t for t in trades if t["result"] == "TP_RUNNER"])
    bes = len([t for t in trades if t["result"] == "BE"])
    losses = len([t for t in trades if t["result"] == "SL"])
    eff_wr = ((wins + bes) / total * 100.0) if total > 0 else 0.0
    tot_prof = sum(t["pnl"] for t in trades if t["pnl"] > 0)
    tot_loss = abs(sum(t["pnl"] for t in trades if t["pnl"] < 0))
    pf = (tot_prof / tot_loss) if tot_loss > 0 else 99.0
    roi = ((balance - initial_balance) / initial_balance) * 100.0
    calmar = (roi / max_dd_pct) if max_dd_pct > 0 else 99.0
    
    return {
        "scenario": scenario_name,
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
    print("="*105)
    print("🔬 MATRIZ DE ESCENARIOS CUANTITATIVOS AVANZADOS (6 MESES DE DATOS REALES CONTINUOS)")
    print("="*105)
    
    scenarios = [
        "A_Baseline_65",
        "B_HighBeta_Runner",
        "C_Regime_Adaptive",
        "D_Killzone_Strict",
        "E_Asymmetric_Alpha_Kelly"
    ]
    
    for sym_name, ticker in TRADFI_TICKERS.items():
        print(f"\n📈 INSTRUMENTO: {sym_name}")
        df = fetch_data(ticker)
        print(f"{'Escenario':<26} | {'Trades':<7} | {'Win Rate Ef.':<13} | {'Profit Factor':<14} | {'Max DD':<9} | {'Calmar':<7} | {'Retorno ($100k)'}")
        print("-" * 105)
        for sc in scenarios:
            res = run_scenario(df, sc)
            print(f"{res['scenario']:<26} | {res['trades']:<7} | {res['eff_wr']:<12.1f}% | {res['profit_factor']:<14.2f} | {res['max_dd_pct']:<8.2f}% | {res['calmar_ratio']:<6.1f} | +${res['final_balance']-100000:<12,.2f} ({res['roi_pct']:+.1f}%)")

if __name__ == "__main__":
    main()
