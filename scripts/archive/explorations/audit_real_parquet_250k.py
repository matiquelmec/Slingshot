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

def simulate_real_trade(df, start_idx, direction, entry, sl, tp1, tp2, tp3, max_bars=96):
    end_idx = min(len(df), start_idx + max_bars)
    hit_tp1 = False
    hit_tp2 = False
    
    for i in range(start_idx, end_idx):
        h = df["high"].iloc[i]
        l = df["low"].iloc[i]
        exit_ts = df["timestamp"].iloc[i]
        
        if direction == "LONG":
            if l <= sl:
                if hit_tp2:
                    return "TP2", 2.0, exit_ts, sl
                elif hit_tp1:
                    return "TP1_BE", 0.5, exit_ts, sl
                else:
                    return "SL", -1.0, exit_ts, sl
            if h >= tp3:
                return "TP3", 3.0, exit_ts, tp3
            if h >= tp2:
                hit_tp2 = True
            if h >= tp1:
                hit_tp1 = True
        else: # SHORT
            if h >= sl:
                if hit_tp2:
                    return "TP2", 2.0, exit_ts, sl
                elif hit_tp1:
                    return "TP1_BE", 0.5, exit_ts, sl
                else:
                    return "SL", -1.0, exit_ts, sl
            if l <= tp3:
                return "TP3", 3.0, exit_ts, tp3
            if l <= tp2:
                hit_tp2 = True
            if l <= tp1:
                hit_tp1 = True

    if hit_tp2:
        return "TP2", 2.0, df["timestamp"].iloc[end_idx-1], tp2
    elif hit_tp1:
        return "TP1_BE", 0.5, df["timestamp"].iloc[end_idx-1], tp1
    return "TIMEOUT", 0.0, df["timestamp"].iloc[end_idx-1], df["close"].iloc[end_idx-1]

async def run_real_parquet_backtest():
    print("=" * 105, flush=True)
    print("🦅 AUDITORÍA 100% REAL SOBRE VELAS HISTÓRICAS DE BINANCE (PARQUET DATA LAKE 180 DÍAS)", flush=True)
    print("=" * 105, flush=True)

    router = SlingshotRouter()
    
    # Cargar referencia BTC para Veto Macro
    btc_file = os.path.join(DATA_DIR, "BTCUSDT_15m_180d.parquet")
    btc_df = pd.read_parquet(btc_file) if os.path.exists(btc_file) else None
    if btc_df is not None:
        btc_df["ema200"] = btc_df["close"].ewm(span=200, adjust=False).mean()

    all_trade_events = []

    for symbol in VIP_20_ASSETS:
        file_path = os.path.join(DATA_DIR, f"{symbol}_15m_180d.parquet")
        if not os.path.exists(file_path):
            continue

        df = pd.read_parquet(file_path)
        df["ema200"] = df["close"].ewm(span=200, adjust=False).mean()
        df["ema800"] = df["close"].ewm(span=min(800, len(df)), adjust=False).mean()
        df["atr"] = (df["high"] - df["low"]).rolling(14).mean()

        window_size = 100
        for i in range(window_size, len(df) - 96, 32): # Paso cada 8 horas
            sub_df = df.iloc[i-window_size:i].copy().reset_index(drop=True)
            current_price = float(sub_df["close"].iloc[-1])
            ema200_val = float(sub_df["ema200"].iloc[-1])
            ema800_val = float(sub_df["ema800"].iloc[-1])
            atr_val = float(sub_df["atr"].iloc[-1]) if not np.isnan(sub_df["atr"].iloc[-1]) else current_price * 0.002
            ts = int(sub_df["timestamp"].iloc[-1])
            
            # Kaufman Efficiency Ratio (KER 20)
            change_ker = abs(sub_df["close"].iloc[-1] - sub_df["close"].iloc[-20])
            vol_ker = sub_df["close"].diff().abs().tail(20).sum()
            ker_val = float(change_ker / vol_ker) if vol_ker > 0 else 0.5

            result = await router.process_market_data(sub_df, asset=symbol, interval="15m", silent=True)
            fib_data = get_current_fibonacci_levels(sub_df)
            liq_clusters = estimate_liquidation_clusters(sub_df, current_price)
            smc_map = result.get("smc", {})

            for direction in ["LONG", "SHORT"]:
                # Veto Macro por BTC
                btc_aligned = True
                if btc_df is not None and symbol != "BTCUSDT":
                    btc_sub = btc_df[btc_df["timestamp"] <= ts]
                    if len(btc_sub) > 0:
                        b_price = float(btc_sub["close"].iloc[-1])
                        b_ema = float(btc_sub["ema200"].iloc[-1])
                        btc_aligned = (direction == "LONG" and b_price > b_ema) or (direction == "SHORT" and b_price < b_ema)

                if not btc_aligned:
                    continue # VETO MACRO BTC APLICADO

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

                # Reglas de Confluencia ELITE y Filtro Anti-Ruido KER
                HIGH_NOISE = ["BNBUSDT", "XRPUSDT", "SOLUSDT", "LINKUSDT"]
                if (ker_val < 0.22 or symbol in HIGH_NOISE) and score < 65:
                    continue

                if sl > 0 and tp1 > 0 and score >= 50 and is_trend_ok and is_htf_aligned:
                    outcome, r_mult, exit_ts, exit_price = simulate_real_trade(df, i, direction, optimal_entry, sl, tp1, tp2, tp3)
                    
                    dt_entry = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
                    dt_exit = datetime.datetime.fromtimestamp(int(exit_ts), tz=datetime.timezone.utc)
                    
                    all_trade_events.append({
                        "entry_time": dt_entry,
                        "exit_time": dt_exit,
                        "timestamp_int": ts,
                        "asset": symbol,
                        "direction": direction,
                        "score": score,
                        "entry_price": optimal_entry,
                        "sl_price": sl,
                        "tp3_price": tp3,
                        "outcome": outcome,
                        "r_mult": r_mult
                    })

    # Ordenar cronológicamente todos los trades ocurridos en el mercado real
    all_trade_events.sort(key=lambda x: x["timestamp_int"])

    # ── SIMULACIÓN CRONOLÓGICA DE LA CUENTA DE $250,000 USD ──
    starting_capital = 250_000.0
    balance = starting_capital
    peak = starting_capital
    max_dd = 0.0
    
    trade_logs = []
    
    for t in all_trade_events:
        # Riesgo del 2% del saldo actual con tope de $10,000 USD para cuidar la liquidez
        risk_usd = min(balance * 0.02, 10_000.0)
        
        # Comisión real de futuros (~0.04% entrada + 0.04% salida = 0.08% sobre tamaño nocional)
        pos_notional = risk_usd / (abs(t["entry_price"] - t["sl_price"]) / t["entry_price"])
        fees = pos_notional * 0.0008
        
        gross_pnl = risk_usd * t["r_mult"]
        net_pnl = gross_pnl - fees
        balance += net_pnl
        
        if balance > peak:
            peak = balance
        dd = (peak - balance) / peak * 100.0
        if dd > max_dd:
            max_dd = dd
            
        trade_logs.append({
            "Fecha Entrada": t["entry_time"].strftime("%Y-%m-%d %H:%M"),
            "Activo": t["asset"],
            "Dir": t["direction"],
            "Score": f"{t['score']}%",
            "Entrada": f"${t['entry_price']:,.2f}",
            "Resultado": t["outcome"],
            "PnL ($)": f"${net_pnl:+,.2f}",
            "Balance ($)": f"${balance:,.2f}"
        })

    df_logs = pd.DataFrame(trade_logs)
    
    print(f"\n✅ Total de Trades Ejecutados en Orden Cronológica: {len(df_logs)}")
    print(f"💰 Capital Inicial: ${starting_capital:,.2f} USD")
    print(f"🚀 Capital Final  : ${balance:,.2f} USD")
    print(f"💵 Ganancia Neta  : +${balance - starting_capital:,.2f} USD (ROI: +{(balance - starting_capital)/starting_capital*100:.1f}%)")
    print(f"📉 Max Drawdown   : -{max_dd:.1f}%")
    print("-" * 105)
    print("\n📋 MUESTRA DE LAS PRIMERAS 15 OPERACIONES REALES EN EL HISTORIAL:")
    print(df_logs.head(15).to_string(index=False))
    print("\n📋 MUESTRA DE LAS ÚLTIMAS 15 OPERACIONES REALES EN EL HISTORIAL:")
    print(df_logs.tail(15).to_string(index=False))
    print("=" * 105)

if __name__ == "__main__":
    asyncio.run(run_real_parquet_backtest())
