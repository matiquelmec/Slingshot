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

def calculate_kaufman_efficiency_ratio(df_window, period=20):
    if len(df_window) < period:
        return 0.5
    change = abs(df_window["close"].iloc[-1] - df_window["close"].iloc[-period])
    volatility = (df_window["close"].diff().abs()).tail(period).sum()
    if volatility == 0:
        return 0.0
    return float(change / volatility)

def simulate_trade_adaptive_tp(df, start_idx, direction, entry, sl, tp1, tp2, tp3, max_holding_bars=96):
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

async def audit_unexplored_frontiers():
    print("=" * 95, flush=True)
    print("🔬 AUDITORÍA DE LAS 4 FRONTERAS CUANTITATIVAS (OPTIMIZACIÓN V12 SOVEREIGN)", flush=True)
    print("=" * 95, flush=True)

    router = SlingshotRouter()
    
    # Pre-cargar BTC para filtro de tendencia macro
    btc_file = os.path.join(DATA_DIR, "BTCUSDT_15m_180d.parquet")
    btc_df = pd.read_parquet(btc_file) if os.path.exists(btc_file) else None
    if btc_df is not None:
        btc_df["ema200"] = btc_df["close"].ewm(span=200, adjust=False).mean()

    results_h = {
        "0. BASE ADAPTATIVA KER (v11.3)": [],
        "H1. FILTRO DE ATR SQUEEZE (Entrar antes de la expansión)": [],
        "H2. VETO ABSOLUTO POR BTC MACRO DIVERGENCE (Alts alineadas con BTC)": [],
        "H3. POSICIONAMIENTO KELLY ADAPTATIVO (Sizing por Confluencia)": [],
        "H4. MASTER COMBINADO (Las 3 Mejoras Juntas)": []
    }

    for symbol in VIP_20_ASSETS:
        file_path = os.path.join(DATA_DIR, f"{symbol}_15m_180d.parquet")
        if not os.path.exists(file_path):
            continue

        df = pd.read_parquet(file_path)
        df["ema200"] = df["close"].ewm(span=200, adjust=False).mean()
        df["ema800"] = df["close"].ewm(span=min(800, len(df)), adjust=False).mean()
        df["atr"] = (df["high"] - df["low"]).rolling(14).mean()
        df["atr_sma"] = df["atr"].rolling(50).mean()

        window_size = 100
        for i in range(window_size, len(df) - 96, 48):
            sub_df = df.iloc[i-window_size:i].copy().reset_index(drop=True)
            current_price = float(sub_df["close"].iloc[-1])
            ema200_val = float(sub_df["ema200"].iloc[-1])
            ema800_val = float(sub_df["ema800"].iloc[-1])
            atr_val = float(sub_df["atr"].iloc[-1])
            atr_sma_val = float(sub_df["atr_sma"].iloc[-1]) if "atr_sma" in sub_df.columns else atr_val
            
            ts = int(sub_df["timestamp"].iloc[-1])
            
            dt_utc = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
            day_name = dt_utc.strftime('%A')
            hour_utc = dt_utc.hour
            is_monday_pre_ny = (day_name == "Monday" and hour_utc < 13)

            ker_20 = calculate_kaufman_efficiency_ratio(sub_df, period=20)
            
            # Chequeo BTC Trend
            btc_trend_aligned = True
            if btc_df is not None and symbol != "BTCUSDT":
                btc_sub = btc_df[btc_df["timestamp"] <= ts]
                if len(btc_sub) > 0:
                    btc_price = float(btc_sub["close"].iloc[-1])
                    btc_ema200 = float(btc_sub["ema200"].iloc[-1])
                    # Si BTC está bajista, no tomar Longs en Alts
                    # Si BTC está alcista, no tomar Shorts en Alts
                    # Se evalúa en el bucle direction

            result = await router.process_market_data(sub_df, asset=symbol, interval="15m", silent=True)
            fib_data = get_current_fibonacci_levels(sub_df)
            liq_clusters = estimate_liquidation_clusters(sub_df, current_price)

            smc_map = result.get("smc", {})

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

                # Evaluamos setup base KER v11.3
                if sl > 0 and tp1 > 0 and score >= 50 and is_trend_ok and is_htf_aligned and not is_monday_pre_ny:
                    if ker_20 < 0.22 and score < 65:
                        continue

                    outcome, pnl = simulate_trade_adaptive_tp(df, i, direction, optimal_entry, sl, tp1, tp2, tp3)

                    # 0. Base v11.3
                    results_h["0. BASE ADAPTATIVA KER (v11.3)"].append(pnl)

                    # H1. ATR Squeeze (No entrar si ATR está sobre-extendido > 1.6x de la media)
                    if atr_val <= (1.6 * atr_sma_val):
                        results_h["H1. FILTRO DE ATR SQUEEZE (Entrar antes de la expansión)"].append(pnl)

                    # H2. Veto por BTC Macro Divergence
                    if btc_df is not None and symbol != "BTCUSDT":
                        btc_sub = btc_df[btc_df["timestamp"] <= ts]
                        if len(btc_sub) > 0:
                            b_price = float(btc_sub["close"].iloc[-1])
                            b_ema200 = float(btc_sub["ema200"].iloc[-1])
                            b_aligned = (direction == "LONG" and b_price > b_ema200) or (direction == "SHORT" and b_price < b_ema200)
                            if b_aligned:
                                results_h["H2. VETO ABSOLUTO POR BTC MACRO DIVERGENCE (Alts alineadas con BTC)"].append(pnl)
                    else:
                        results_h["H2. VETO ABSOLUTO POR BTC MACRO DIVERGENCE (Alts alineadas con BTC)"].append(pnl)

                    # H3. Kelly Sizing por Confluencia (Score >= 70 = 1.5x PnL, Score < 70 = 1.0x PnL)
                    multiplier_kelly = 1.5 if score >= 70 else 1.0
                    results_h["H3. POSICIONAMIENTO KELLY ADAPTATIVO (Sizing por Confluencia)"].append(pnl * multiplier_kelly)

                    # H4. Master Combinado (H1 + H2 + H3)
                    is_h1_pass = atr_val <= (1.6 * atr_sma_val)
                    is_h2_pass = True
                    if btc_df is not None and symbol != "BTCUSDT":
                        btc_sub = btc_df[btc_df["timestamp"] <= ts]
                        if len(btc_sub) > 0:
                            b_price = float(btc_sub["close"].iloc[-1])
                            b_ema200 = float(btc_sub["ema200"].iloc[-1])
                            is_h2_pass = (direction == "LONG" and b_price > b_ema200) or (direction == "SHORT" and b_price < b_ema200)

                    if is_h1_pass and is_h2_pass:
                        results_h["H4. MASTER COMBINADO (Las 3 Mejoras Juntas)"].append(pnl * multiplier_kelly)

    print("\n" + "=" * 95, flush=True)
    print("📊 RESULTADOS EMPÍRICOS DE LAS FRONTERAS CUANTITATIVAS (6 MESES)", flush=True)
    print("=" * 95, flush=True)

    for h_name, pnls in results_h.items():
        total_t = len(pnls)
        if total_t == 0: continue
        wins = sum(1 for p in pnls if p > 0)
        losses = sum(1 for p in pnls if p < 0)
        net_pnl = sum(pnls)
        win_rate = (wins / total_t * 100) if total_t > 0 else 0
        pf = (sum(p for p in pnls if p > 0) / abs(sum(p for p in pnls if p < 0))) if sum(p for p in pnls if p < 0) < 0 else 99.0

        print(f"\n🚀 {h_name}:", flush=True)
        print(f"   • Total Trades Evaluados : {total_t}", flush=True)
        print(f"   • Ganadoras / Perdedoras : {wins} / {losses}", flush=True)
        print(f"   • Win Rate (Acierto)     : {win_rate:.2f}%", flush=True)
        print(f"   • Beneficio Neto Realizado: ${net_pnl:+,.2f} USDT", flush=True)
        print(f"   • Profit Factor Estándar : {pf:.2f}", flush=True)

    print("=" * 95, flush=True)

if __name__ == "__main__":
    asyncio.run(audit_unexplored_frontiers())
