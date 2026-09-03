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
    if 0 <= hour < 8:
        sess = "ASIA"
    elif 8 <= hour < 14:
        sess = "LONDON"
    else:
        sess = "NEW_YORK"
    return {"current_session": sess, "is_killzone": 8 <= hour < 17, "day_of_week": dt.strftime('%A')}

def simulate_trade(df, start_idx, direction, entry, sl, tp1, tp2, tp3, max_holding_bars=96):
    """
    Simula la evolución barra a barra de la orden en los datos futuros.
    Returns: outcome ('TP1', 'TP2', 'TP3', 'SL', 'TIMEOUT'), max_rr, pnl_usd
    """
    risk_dist = abs(entry - sl)
    if risk_dist == 0:
        return "SL", 0.0, -100.0
    
    end_idx = min(len(df), start_idx + max_holding_bars)
    hit_tp1 = False
    hit_tp2 = False
    
    for i in range(start_idx, end_idx):
        high = df["high"].iloc[i]
        low = df["low"].iloc[i]
        
        if direction == "LONG":
            # Verificar SL primero (conservador)
            if low <= sl:
                if hit_tp2:
                    return "TP2", 2.0, 150.0  # Parcial TP1 + TP2 asegurado
                elif hit_tp1:
                    return "TP1", 1.0, 50.0   # Parcial TP1 asegurado, resto a BE
                else:
                    return "SL", -1.0, -100.0 # -$100 fixed risk
            if high >= tp3:
                return "TP3", 3.0, 300.0
            if high >= tp2:
                hit_tp2 = True
            if high >= tp1:
                hit_tp1 = True
        else:  # SHORT
            if high >= sl:
                if hit_tp2:
                    return "TP2", 2.0, 150.0
                elif hit_tp1:
                    return "TP1", 1.0, 50.0
                else:
                    return "SL", -1.0, -100.0
            if low <= tp3:
                return "TP3", 3.0, 300.0
            if low <= tp2:
                hit_tp2 = True
            if low <= tp1:
                hit_tp1 = True

    if hit_tp2:
        return "TP2", 2.0, 150.0
    elif hit_tp1:
        return "TP1", 1.0, 50.0
    return "TIMEOUT", 0.0, 0.0

async def run_scanner_backtest():
    print("=" * 90)
    print("📊 BACKTEST OFICIAL DEL ESCÁNER DE OPORTUNIDADES — ANÁLISIS DE CONFLUENCIA > 50%")
    print("=" * 90)

    router = SlingshotRouter()
    
    thresholds = [35, 40, 45, 50, 60, 70]
    threshold_results = {t: {"trades": [], "wins": 0, "losses": 0, "net_pnl": 0.0} for t in thresholds}

    for file_name in FILES:
        file_path = os.path.join(DATA_DIR, file_name)
        if not os.path.exists(file_path):
            continue

        symbol = file_name.split("_")[0]
        df = pd.read_parquet(file_path)
        rename_map = {'t': 'timestamp', 'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume'}
        df = df.rename(columns=rename_map)
        print(f"\n🔬 Auditando Escáner para {symbol} (90 días / {len(df)} velas de 15m)...")

        window_size = 100
        # Muestreo cada 32 velas (8 horas) para simular escaneos independientes rápidos
        for i in range(window_size, len(df) - 96, 32):
            sub_df = df.iloc[i-window_size:i].copy().reset_index(drop=True)
            current_price = float(sub_df["close"].iloc[-1])
            ts = int(sub_df["timestamp"].iloc[-1])
            
            result = await router.process_market_data(sub_df, asset=symbol, interval="15m", silent=True)
            fib_data = get_current_fibonacci_levels(sub_df)
            session_data = calculate_session_mock(ts)
            liq_clusters = estimate_liquidation_clusters(sub_df, current_price)

            smc_map = result.get("smc", {})
            atr_val = float(sub_df["atr"].iloc[-1]) if "atr" in sub_df.columns else float(current_price * 0.002)

            for direction in ["LONG", "SHORT"]:
                # Calcular entrada límite SMC
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
                    "asset": symbol,
                    "symbol": symbol,
                    "type": "Estructura Local",
                    "signal_type": direction,
                    "price": optimal_entry,
                    "timestamp": str(ts),
                    "atr_value": atr_val,
                }

                risk_data = router._risk.calculate_position(
                    current_price=optimal_entry,
                    signal_type=direction,
                    market_regime=(result.get("diagnostic") or {}).get("regime", "RANGING"),
                    smc_data=smc_map,
                    atr_value=atr_val,
                    asset=symbol,
                    liquidations=liq_clusters
                )

                conf_res = confluence_manager.evaluate_signal(
                    sub_df,
                    virtual_sig,
                    smc_map=smc_map,
                    fib_data=fib_data,
                    session_data=session_data,
                    interval="15m",
                    liquidations=liq_clusters
                )

                score = conf_res.get("score", 0)

                for t in thresholds:
                    if score >= t:
                        sl = risk_data.get("stop_loss", 0)
                        tp1 = risk_data.get("tp1", 0)
                        tp2 = risk_data.get("tp2", 0)
                        tp3 = risk_data.get("tp3", 0)

                        if sl > 0 and tp1 > 0:
                            outcome, rr, pnl = simulate_trade(df, i, direction, optimal_entry, sl, tp1, tp2, tp3)
                            
                            threshold_results[t]["trades"].append({
                                "symbol": symbol,
                                "direction": direction,
                                "score": score,
                                "outcome": outcome,
                                "pnl": pnl
                            })
                            if pnl > 0:
                                threshold_results[t]["wins"] += 1
                            elif pnl < 0:
                                threshold_results[t]["losses"] += 1
                            threshold_results[t]["net_pnl"] += pnl

    print("\n" + "=" * 90)
    print("📈 COMPARATIVA DE RENDIMIENTO POR UMBRAL DE CONFLUENCIA ($100 RISK POR TRADE)")
    print("=" * 90)

    for t in thresholds:
        res = threshold_results[t]
        total_t = len(res["trades"])
        wins = res["wins"]
        losses = res["losses"]
        win_rate = (wins / total_t * 100) if total_t > 0 else 0.0
        pnl = res["net_pnl"]
        pf = (wins * 150.0 / (losses * 100.0)) if losses > 0 else (99.0 if wins > 0 else 0.0)

        print(f"\n🎯 UMBRAL DE CONFLUENCIA > {t}%:")
        print(f"   • Total Oportunidades Evaluadas: {total_t}")
        print(f"   • Ganadoras / Perdedoras       : {wins} / {losses}")
        print(f"   • Tasa de Acierto (Win Rate)   : {win_rate:.2f}%")
        print(f"   • Beneficio Neto ($100 Risk)   : ${pnl:+,.2f} USDT")
        print(f"   • Profit Factor Estándar       : {pf:.2f}")

    print("\n" + "=" * 90)

if __name__ == "__main__":
    asyncio.run(run_scanner_backtest())
