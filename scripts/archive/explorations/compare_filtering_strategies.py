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

VIP_20_ASSETS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "LINKUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "DOTUSDT", "NEARUSDT", "SUIUSDT",
    "FETUSDT", "INJUSDT", "ARBUSDT", "OPUSDT", "RENDERUSDT", "ATOMUSDT",
    "TIAUSDT", "APTUSDT"
]

TOP_5 = ["ETHUSDT", "BTCUSDT", "RENDERUSDT", "ATOMUSDT", "TIAUSDT"]
TOP_10 = ["ETHUSDT", "BTCUSDT", "RENDERUSDT", "ATOMUSDT", "TIAUSDT", "ADAUSDT", "SUIUSDT", "DOTUSDT", "NEARUSDT", "FETUSDT"]

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

async def compare_filtering_strategies():
    print("=" * 95, flush=True)
    print("📊 EVALUACIÓN COMPARATIVA: FILTRADO INTELIGENTE (TOP 5 vs TOP 10 vs FILTRO DE RUIDO)", flush=True)
    print("=" * 95, flush=True)

    router = SlingshotRouter()
    
    strategies = {
        "1. TODOS LOS 20 ACTIVOS (Sin Filtro de Selección)": [],
        "2. ESTRATEGIA TOP 5 ACTIVOS (ETH, BTC, RENDER, ATOM, TIA)": [],
        "3. ESTRATEGIA TOP 10 ACTIVOS (Los 10 Mejores Productores)": [],
        "4. ESTRATEGIA FILTRO ANTI-RUIDO (Excluye Activos con Whipsaws: BNB, XRP, SOL, LINK)": [],
        "5. ESTRATEGIA HÍBRIDA MAJORS ALWAYS + ALTS SOLO KILLZONES (Máxima Eficiencia)": []
    }

    for symbol in VIP_20_ASSETS:
        file_path = os.path.join(DATA_DIR, f"{symbol}_15m_180d.parquet")
        if not os.path.exists(file_path):
            continue

        df = pd.read_parquet(file_path)
        df["ema200"] = df["close"].ewm(span=200, adjust=False).mean()
        df["ema800"] = df["close"].ewm(span=min(800, len(df)), adjust=False).mean()

        window_size = 100
        for i in range(window_size, len(df) - 96, 48):
            sub_df = df.iloc[i-window_size:i].copy().reset_index(drop=True)
            current_price = float(sub_df["close"].iloc[-1])
            ema200_val = float(sub_df["ema200"].iloc[-1])
            ema800_val = float(sub_df["ema800"].iloc[-1])
            ts = int(sub_df["timestamp"].iloc[-1])
            
            dt_utc = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
            day_name = dt_utc.strftime('%A')
            hour_utc = dt_utc.hour

            is_monday_pre_ny = (day_name == "Monday" and hour_utc < 13)
            is_killzone = (7 <= hour_utc < 10) or (13 <= hour_utc < 16)
            
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
                is_htf_aligned = (direction == "LONG" and current_price > ema800_val) or (direction == "SHORT" and current_price < ema800_val)

                sl = risk_data.get("stop_loss", 0)
                tp1 = risk_data.get("tp1", 0)
                tp2 = risk_data.get("tp2", 0)
                tp3 = risk_data.get("tp3", 0)

                if sl > 0 and tp1 > 0 and score >= 50 and is_trend_ok and is_htf_aligned and not is_monday_pre_ny:
                    outcome, pnl = simulate_trade(df, i, direction, optimal_entry, sl, tp1, tp2, tp3)

                    # 1. Todos los 20
                    strategies["1. TODOS LOS 20 ACTIVOS (Sin Filtro de Selección)"].append(pnl)

                    # 2. Top 5
                    if symbol in TOP_5:
                        strategies["2. ESTRATEGIA TOP 5 ACTIVOS (ETH, BTC, RENDER, ATOM, TIA)"].append(pnl)

                    # 3. Top 10
                    if symbol in TOP_10:
                        strategies["3. ESTRATEGIA TOP 10 ACTIVOS (Los 10 Mejores Productores)"].append(pnl)

                    # 4. Anti-Ruido (Excluye BNB, XRP, SOL, LINK)
                    if symbol not in ["BNBUSDT", "XRPUSDT", "SOLUSDT", "LINKUSDT"]:
                        strategies["4. ESTRATEGIA FILTRO ANTI-RUIDO (Excluye Activos con Whipsaws: BNB, XRP, SOL, LINK)"].append(pnl)

                    # 5. Híbrida: Majors siempre, Alts solo en Killzones
                    if symbol in ["BTCUSDT", "ETHUSDT"]:
                        strategies["5. ESTRATEGIA HÍBRIDA MAJORS ALWAYS + ALTS SOLO KILLZONES (Máxima Eficiencia)"].append(pnl)
                    elif is_killzone and symbol not in ["BNBUSDT", "XRPUSDT"]:
                        strategies["5. ESTRATEGIA HÍBRIDA MAJORS ALWAYS + ALTS SOLO KILLZONES (Máxima Eficiencia)"].append(pnl)

    print("\n" + "=" * 95, flush=True)
    print("📊 RESULTADOS MATEMÁTICOS DE LAS ESTRATEGIAS DE FILTRADO (6 MESES)", flush=True)
    print("=" * 95, flush=True)

    for st_name, pnls in strategies.items():
        total_t = len(pnls)
        if total_t == 0: continue
        wins = sum(1 for p in pnls if p > 0)
        losses = sum(1 for p in pnls if p < 0)
        net_pnl = sum(pnls)
        win_rate = (wins / total_t * 100)
        pf = (wins * 200.0 / (losses * 100.0)) if losses > 0 else (99.0 if wins > 0 else 0.0)

        print(f"\n🚀 {st_name}:", flush=True)
        print(f"   • Total Trades Evaluados : {total_t}", flush=True)
        print(f"   • Ganadoras / Perdedoras : {wins} / {losses}", flush=True)
        print(f"   • Win Rate (Acierto)     : {win_rate:.2f}%", flush=True)
        print(f"   • Beneficio Neto Realizado: ${net_pnl:+,.2f} USDT", flush=True)
        print(f"   • Profit Factor Estándar : {pf:.2f}", flush=True)

    print("\n" + "=" * 95, flush=True)

if __name__ == "__main__":
    asyncio.run(compare_filtering_strategies())
