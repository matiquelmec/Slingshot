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
    "BTCUSDT_15m_90d.parquet",
    "ETHUSDT_15m_90d.parquet",
    "SOLUSDT_15m_90d.parquet",
    "BNBUSDT_15m_90d.parquet",
    "LINKUSDT_15m_90d.parquet",
    "XRPUSDT_15m_90d.parquet"
]

def calculate_session_mock(ts):
    dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
    hour = dt.hour
    sess = "ASIA" if 0 <= hour < 8 else ("LONDON" if 8 <= hour < 14 else "NEW_YORK")
    return {"current_session": sess, "is_killzone": 8 <= hour < 17, "day_of_week": dt.strftime('%A')}

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
                    return "TP2", 200.0  # R:R 2.0+
                elif hit_tp1:
                    return "TP1", 100.0  # R:R 1.0+
                else:
                    return "SL", -100.0
            if high >= tp3:
                return "TP3", 350.0
            if high >= tp2:
                hit_tp2 = True
            if high >= tp1:
                hit_tp1 = True
        else:  # SHORT
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

async def run_optimized_backtest():
    print("=" * 90)
    print("🚀 OPTIMIZACIÓN INSTITUCIONAL DEL ESCÁNER — APLICANDO REGLAS DE ALTO RENDIMIENTO")
    print("=" * 90)

    router = SlingshotRouter()
    
    modes = {
        "BASE (>50% Confluencia Sin Filtros Extra)": {"wins": 0, "losses": 0, "net_pnl": 0.0, "trades": []},
        "OPCIÓN A: + Filtro Trend EMA 200": {"wins": 0, "losses": 0, "net_pnl": 0.0, "trades": []},
        "OPCIÓN B: + Filtro RVOL >= 1.2x (Interés Volumen)": {"wins": 0, "losses": 0, "net_pnl": 0.0, "trades": []},
        "OPCIÓN C: + R:R Mínimo 2.5:1 Exigido": {"wins": 0, "losses": 0, "net_pnl": 0.0, "trades": []},
        "OPCIÓN SUPREMA: Filtro Combinado Trend + RVOL + R:R >= 2.5": {"wins": 0, "losses": 0, "net_pnl": 0.0, "trades": []}
    }

    for file_name in FILES:
        file_path = os.path.join(DATA_DIR, file_name)
        if not os.path.exists(file_path):
            continue

        symbol = file_name.split("_")[0]
        df = pd.read_parquet(file_path)
        rename_map = {'t': 'timestamp', 'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume'}
        df = df.rename(columns=rename_map)
        
        # Calcular EMA 200
        df["ema200"] = df["close"].ewm(span=200, adjust=False).mean()
        # Calcular RVOL (Volumen / SMA 20 del volumen)
        df["vol_sma"] = df["volume"].rolling(20).mean()
        df["rvol"] = df["volume"] / (df["vol_sma"] + 1e-9)

        print(f"🔬 Evaluando optimizaciones para {symbol}...")

        window_size = 100
        for i in range(window_size, len(df) - 96, 24):
            sub_df = df.iloc[i-window_size:i].copy().reset_index(drop=True)
            current_price = float(sub_df["close"].iloc[-1])
            ema200_val = float(sub_df["ema200"].iloc[-1])
            rvol_val = float(sub_df["rvol"].iloc[-1])
            ts = int(sub_df["timestamp"].iloc[-1])
            
            result = await router.process_market_data(sub_df, asset=symbol, interval="15m", silent=True)
            fib_data = get_current_fibonacci_levels(sub_df)
            session_data = calculate_session_mock(ts)
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
                    session_data=session_data, interval="15m", liquidations=liq_clusters
                )

                score = conf_res.get("score", 0)

                if score >= 50:
                    sl = risk_data.get("stop_loss", 0)
                    tp1 = risk_data.get("tp1", 0)
                    tp2 = risk_data.get("tp2", 0)
                    tp3 = risk_data.get("tp3", 0)

                    if sl > 0 and tp1 > 0:
                        risk_dist = abs(optimal_entry - sl)
                        tp2_dist = abs(tp2 - optimal_entry)
                        rr_ratio = tp2_dist / (risk_dist + 1e-9)
                        
                        outcome, pnl = simulate_trade(df, i, direction, optimal_entry, sl, tp1, tp2, tp3)

                        # Evaluacion por modos
                        is_trend_ok = (direction == "LONG" and current_price > ema200_val) or (direction == "SHORT" and current_price < ema200_val)
                        is_rvol_ok = rvol_val >= 1.2
                        is_rr_ok = rr_ratio >= 2.5

                        # 1. Base
                        modes["BASE (>50% Confluencia Sin Filtros Extra)"]["trades"].append(pnl)

                        # 2. Trend
                        if is_trend_ok:
                            modes["OPCIÓN A: + Filtro Trend EMA 200"]["trades"].append(pnl)

                        # 3. RVOL
                        if is_rvol_ok:
                            modes["OPCIÓN B: + Filtro RVOL >= 1.2x (Interés Volumen)"]["trades"].append(pnl)

                        # 4. RR
                        if is_rr_ok:
                            modes["OPCIÓN C: + R:R Mínimo 2.5:1 Exigido"]["trades"].append(pnl)

                        # 5. Suprema
                        if is_trend_ok and is_rvol_ok and is_rr_ok:
                            modes["OPCIÓN SUPREMA: Filtro Combinado Trend + RVOL + R:R >= 2.5"]["trades"].append(pnl)

    print("\n" + "=" * 90)
    print("📊 RESULTADOS COMPARATIVOS DE OPTIMIZACIÓN (90 DÍAS DE DATOS)")
    print("=" * 90)

    for mode_name, data in modes.items():
        pnls = data["trades"]
        total_t = len(pnls)
        wins = sum(1 for p in pnls if p > 0)
        losses = sum(1 for p in pnls if p < 0)
        net_pnl = sum(pnls)
        win_rate = (wins / total_t * 100) if total_t > 0 else 0.0
        pf = (wins * 200.0 / (losses * 100.0)) if losses > 0 else (99.0 if wins > 0 else 0.0)

        print(f"\n🚀 {mode_name}:")
        print(f"   • Total Trades          : {total_t}")
        print(f"   • Ganadoras / Perdedoras: {wins} / {losses}")
        print(f"   • Win Rate (Acierto)    : {win_rate:.2f}%")
        print(f"   • Beneficio Neto        : ${net_pnl:+,.2f} USDT")
        print(f"   • Profit Factor         : {pf:.2f}")

    print("\n" + "=" * 90)

if __name__ == "__main__":
    asyncio.run(run_optimized_backtest())
