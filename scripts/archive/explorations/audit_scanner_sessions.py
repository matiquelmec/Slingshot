import os
os.environ["DISABLE_AI_VALIDATOR"] = "true"

import asyncio
import pandas as pd
import numpy as np
import datetime
from engine.main_router import SlingshotRouter
from engine.core.confluence import confluence_manager
from engine.indicators.liquidations import estimate_liquidation_clusters
from engine.indicators.fibonacci import get_current_fibonacci_levels

DATA_DIR = os.path.join("engine", "backtest", "data")
FILES = [
    "BTCUSDT_15m_180d.parquet",
    "ETHUSDT_15m_180d.parquet",
    "SOLUSDT_15m_180d.parquet",
    "BNBUSDT_15m_180d.parquet",
    "LINKUSDT_15m_180d.parquet",
    "XRPUSDT_15m_180d.parquet"
]

def classify_session_details(ts):
    dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
    hour = dt.hour
    
    # Clasificación por Sesiones Institucionales (UTC)
    if 0 <= hour < 7:
        sess = "ASIA (00:00-07:00 UTC)"
    elif 7 <= hour < 12:
        sess = "LONDRES (07:00-12:00 UTC)"
    elif 12 <= hour < 17:
        sess = "NUEVA YORK (12:00-17:00 UTC) 🚀"
    else:
        sess = "CIERRE NY / PACÍFICO (17:00-24:00 UTC)"
        
    is_killzone = (7 <= hour < 10) or (12 <= hour < 16)
    
    return {
        "hour_utc": hour,
        "session": sess,
        "is_killzone": is_killzone,
        "day_of_week": dt.strftime('%A')
    }

def simulate_trade(df, start_idx, direction, entry, sl, tp1, tp2, tp3, max_holding_bars=96):
    risk_dist = abs(entry - sl)
    if risk_dist == 0:
        return "SL", -100.0
    
    end_idx = min(len(df), start_idx + max_holding_bars)
    hit_tp1 = False
    hit_tp2 = False
    
    for i in range(start_idx, end_idx):
        high = df["high"].iloc[i]
        low = df["low"].iloc[i]
        
        if direction == "LONG":
            if low <= sl:
                if hit_tp2:
                    return "TP2", 200.0
                elif hit_tp1:
                    return "TP1", 100.0
                else:
                    return "SL", -100.0
            if high >= tp3:
                return "TP3", 350.0
            if high >= tp2:
                hit_tp2 = True
            if high >= tp1:
                hit_tp1 = True
        else:
            if high >= sl:
                if hit_tp2:
                    return "TP2", 200.0
                elif hit_tp1:
                    return "TP1", 100.0
                else:
                    return "SL", -100.0
            if low <= tp3:
                return "TP3", 350.0
            if low <= tp2:
                hit_tp2 = True
            if low <= tp1:
                hit_tp1 = True

    if hit_tp2:
        return "TP2", 200.0
    elif hit_tp1:
        return "TP1", 100.0
    return "TIMEOUT", 0.0

async def run_session_audit():
    print("=" * 95)
    print("⏰ AUDITORÍA DE RENDIMIENTO POR HORARIO Y SESIÓN INSTITUCIONAL (6 MESES DE DATOS)")
    print("=" * 95)

    router = SlingshotRouter()
    
    session_stats = {}
    killzone_stats = {"KILLZONE (Londres / NY Open)": [], "FUERA DE KILLZONE": []}
    hourly_stats = {h: [] for h in range(24)}

    for file_name in FILES:
        file_path = os.path.join(DATA_DIR, file_name)
        if not os.path.exists(file_path):
            continue

        symbol = file_name.split("_")[0]
        df = pd.read_parquet(file_path)
        df["ema200"] = df["close"].ewm(span=200, adjust=False).mean()

        window_size = 100
        # Muestreo cada 48 velas (12 horas)
        for i in range(window_size, len(df) - 96, 48):
            sub_df = df.iloc[i-window_size:i].copy().reset_index(drop=True)
            current_price = float(sub_df["close"].iloc[-1])
            ema200_val = float(sub_df["ema200"].iloc[-1])
            ts = int(sub_df["timestamp"].iloc[-1])
            
            sess_info = classify_session_details(ts)
            sess_name = sess_info["session"]
            hour_utc = sess_info["hour_utc"]
            is_kz = sess_info["is_killzone"]
            
            result = await router.process_market_data(sub_df, asset=symbol, interval="15m", silent=True)
            fib_data = get_current_fibonacci_levels(sub_df)
            liq_clusters = estimate_liquidation_clusters(sub_df, current_price)

            smc_map = result.get("smc", {})
            atr_val = float(sub_df["atr"].iloc[-1]) if "atr" in sub_df.columns else float(current_price * 0.002)

            for direction in ["LONG", "SHORT"]:
                optimal_entry = current_price
                if direction == "LONG":
                    bull_obs = smc_map.get("order_blocks", {}).get("bullish", []) if smc_map else []
                    valid_obs = [ob for ob in bull_obs if ob.get("top", 0) < current_price]
                    if valid_obs:
                        optimal_entry = max(valid_obs, key=lambda ob: ob["top"])["top"]
                else:
                    bear_obs = smc_map.get("order_blocks", {}).get("bearish", []) if smc_map else []
                    valid_obs = [ob for ob in bear_obs if ob.get("bottom", 0) > current_price]
                    if valid_obs:
                        optimal_entry = min(valid_obs, key=lambda ob: ob["bottom"])["bottom"]

                virtual_sig = {
                    "asset": symbol, "symbol": symbol, "type": "Estructura Local",
                    "signal_type": direction, "price": optimal_entry, "timestamp": str(ts), "atr_value": atr_val
                }

                risk_data = router._risk.calculate_position(
                    current_price=optimal_entry, signal_type=direction,
                    market_regime=(result.get("diagnostic") or {}).get("regime", "RANGING"),
                    smc_data=smc_map, atr_value=atr_val, asset=symbol, liquidations=liq_clusters
                )

                conf_res = confluence_manager.evaluate_signal(
                    sub_df, virtual_sig, smc_map=smc_map, fib_data=fib_data,
                    session_data=sess_info, interval="15m", liquidations=liq_clusters
                )

                score = conf_res.get("score", 0)
                is_trend_ok = (direction == "LONG" and current_price > ema200_val) or (direction == "SHORT" and current_price < ema200_val)

                # Evaluamos señales con confluencia > 50% y filtro Trend OK
                if score >= 50 and is_trend_ok:
                    sl = risk_data.get("stop_loss", 0)
                    tp1 = risk_data.get("tp1", 0)
                    tp2 = risk_data.get("tp2", 0)
                    tp3 = risk_data.get("tp3", 0)

                    if sl > 0 and tp1 > 0:
                        outcome, pnl = simulate_trade(df, i, direction, optimal_entry, sl, tp1, tp2, tp3)

                        # Registrar en sesión
                        if sess_name not in session_stats:
                            session_stats[sess_name] = []
                        session_stats[sess_name].append(pnl)

                        # Registrar en killzone
                        kz_key = "KILLZONE (Londres / NY Open)" if is_kz else "FUERA DE KILLZONE"
                        killzone_stats[kz_key].append(pnl)

                        # Registrar por hora
                        hourly_stats[hour_utc].append(pnl)

    print("\n" + "=" * 95)
    print("🌍 RENDIMIENTO DESGLOSADO POR SESIÓN INSTITUCIONAL")
    print("=" * 95)

    for sess_name, pnls in session_stats.items():
        total_t = len(pnls)
        wins = sum(1 for p in pnls if p > 0)
        losses = sum(1 for p in pnls if p < 0)
        net_pnl = sum(pnls)
        win_rate = (wins / total_t * 100) if total_t > 0 else 0.0
        pf = (wins * 200.0 / (losses * 100.0)) if losses > 0 else (99.0 if wins > 0 else 0.0)

        print(f"\n📊 {sess_name}:")
        print(f"   • Total Trades          : {total_t}")
        print(f"   • Ganadoras / Perdedoras: {wins} / {losses}")
        print(f"   • Win Rate (Acierto)    : {win_rate:.2f}%")
        print(f"   • Beneficio Neto        : ${net_pnl:+,.2f} USDT")
        print(f"   • Profit Factor         : {pf:.2f}")

    print("\n" + "=" * 95)
    print("⚡ COMPARATIVA: KILLZONES DE VOLUMEN vs HORAS REGULARES")
    print("=" * 95)

    for kz_key, pnls in killzone_stats.items():
        total_t = len(pnls)
        wins = sum(1 for p in pnls if p > 0)
        losses = sum(1 for p in pnls if p < 0)
        net_pnl = sum(pnls)
        win_rate = (wins / total_t * 100) if total_t > 0 else 0.0
        pf = (wins * 200.0 / (losses * 100.0)) if losses > 0 else (99.0 if wins > 0 else 0.0)

        print(f"\n🎯 {kz_key}:")
        print(f"   • Total Trades          : {total_t}")
        print(f"   • Ganadoras / Perdedoras: {wins} / {losses}")
        print(f"   • Win Rate (Acierto)    : {win_rate:.2f}%")
        print(f"   • Beneficio Neto        : ${net_pnl:+,.2f} USDT")
        print(f"   • Profit Factor         : {pf:.2f}")

    print("\n" + "=" * 95)

if __name__ == "__main__":
    asyncio.run(run_session_audit())
