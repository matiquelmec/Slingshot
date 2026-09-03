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

async def run_hourly_deep():
    print("=" * 95)
    print("⏰ AUDITORÍA HISTÓRICA COMPLETA DE RENDIMIENTO HORA POR HORA (UTC / EST / CHILE)")
    print("=" * 95)

    router = SlingshotRouter()
    hourly_trades = {h: [] for h in range(24)}

    for file_name in FILES:
        file_path = os.path.join(DATA_DIR, file_name)
        if not os.path.exists(file_path):
            continue

        symbol = file_name.split("_")[0]
        df = pd.read_parquet(file_path)
        df["ema200"] = df["close"].ewm(span=200, adjust=False).mean()

        window_size = 100
        for i in range(window_size, len(df) - 96, 24):
            sub_df = df.iloc[i-window_size:i].copy().reset_index(drop=True)
            current_price = float(sub_df["close"].iloc[-1])
            ema200_val = float(sub_df["ema200"].iloc[-1])
            ts = int(sub_df["timestamp"].iloc[-1])
            
            dt_utc = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
            hour_utc = dt_utc.hour
            
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
                    session_data={"current_session": "NY", "is_killzone": True}, interval="15m", liquidations=liq_clusters
                )

                score = conf_res.get("score", 0)
                is_trend_ok = (direction == "LONG" and current_price > ema200_val) or (direction == "SHORT" and current_price < ema200_val)

                if score >= 50 and is_trend_ok:
                    sl = risk_data.get("stop_loss", 0)
                    tp1 = risk_data.get("tp1", 0)
                    tp2 = risk_data.get("tp2", 0)
                    tp3 = risk_data.get("tp3", 0)

                    if sl > 0 and tp1 > 0:
                        outcome, pnl = simulate_trade(df, i, direction, optimal_entry, sl, tp1, tp2, tp3)
                        hourly_trades[hour_utc].append(pnl)

    print("\n" + "=" * 95)
    print("🕒 DESGLOSE HORA POR HORA (00:00 A 23:00 UTC) — OPTIMIZACIÓN TEMPORAL")
    print("=" * 95)

    print(f"{'Hora UTC':<10} | {'Hora Chile (CLT)':<18} | {'Trades':<8} | {'Win Rate':<10} | {'PnL Neto ($)':<14} | {'Profit Factor':<12}")
    print("-" * 95)

    for h in range(24):
        pnls = hourly_trades[h]
        total_t = len(pnls)
        if total_t == 0:
            continue
        wins = sum(1 for p in pnls if p > 0)
        losses = sum(1 for p in pnls if p < 0)
        net_pnl = sum(pnls)
        win_rate = (wins / total_t * 100)
        pf = (wins * 200.0 / (losses * 100.0)) if losses > 0 else (99.0 if wins > 0 else 0.0)

        # Hora Chile (UTC-3 o UTC-4 según época, UTC-3 actual)
        clt_hour = (h - 3) % 24

        print(f"{h:02d}:00 UTC   | {clt_hour:02d}:00 CLT           | {total_t:<8} | {win_rate:6.1f}%   | ${net_pnl:+12,.2f} | {pf:10.2f}")

    print("=" * 95)

if __name__ == "__main__":
    asyncio.run(run_hourly_deep())
