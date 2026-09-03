import os
os.environ["DISABLE_AI_VALIDATOR"] = "true"

import asyncio
import pandas as pd
import numpy as np
import datetime
import requests
from engine.main_router import SlingshotRouter
from engine.core.confluence import confluence_manager
from engine.indicators.liquidations import estimate_liquidation_clusters
from engine.indicators.fibonacci import get_current_fibonacci_levels

DATA_DIR = os.path.join("engine", "backtest", "data")
os.makedirs(DATA_DIR, exist_ok=True)

VIP_20_ASSETS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "LINKUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "DOTUSDT", "NEARUSDT", "SUIUSDT",
    "FETUSDT", "INJUSDT", "ARBUSDT", "OPUSDT", "RENDERUSDT", "ATOMUSDT",
    "TIAUSDT", "APTUSDT"
]

def download_asset_data(symbol, days=180):
    file_path = os.path.join(DATA_DIR, f"{symbol}_15m_180d.parquet")
    if os.path.exists(file_path):
        print(f"📦 {symbol}: Data local cargada.", flush=True)
        return file_path
    
    print(f"📥 Descargando data de 180 días para {symbol} desde Binance Futures...", flush=True)
    end_time = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
    start_time = end_time - (days * 24 * 60 * 60 * 1000)
    
    all_candles = []
    current_start = start_time
    
    while current_start < end_time:
        url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval=15m&startTime={current_start}&limit=1500"
        try:
            r = requests.get(url, timeout=10)
            data = r.json()
            if not data or not isinstance(data, list) or len(data) == 0:
                break
            all_candles.extend(data)
            current_start = data[-1][0] + 1
            if len(data) < 1500:
                break
        except Exception as e:
            print(f"Error descargando {symbol}: {e}", flush=True)
            break
            
    if len(all_candles) > 0:
        df = pd.DataFrame(all_candles, columns=[
            "timestamp", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "number_of_trades",
            "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume", "ignore"
        ])
        df["timestamp"] = df["timestamp"] // 1000
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
        df.to_parquet(file_path)
        print(f"✅ {symbol}: {len(df)} velas guardadas.", flush=True)
        return file_path
    return None

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

async def audit_all_20_assets():
    print("=" * 95)
    print("🚀 AUDITORÍA MASIVA CUANTITATIVA: LOS 20 ACTIVOS VIP (6 MESES / 345,600 VELAS)")
    print("=" * 95)

    # 1. Asegurar descarga de los 20 activos
    downloaded_files = []
    for sym in VIP_20_ASSETS:
        fp = download_asset_data(sym, days=180)
        if fp:
            downloaded_files.append((sym, fp))

    print(f"\n✅ Data lista para {len(downloaded_files)} activos.")

    router = SlingshotRouter()
    
    scenarios = {
        "1. TODOS LOS 20 ACTIVOS (Confluencia >= 50% + EMA200 15m)": [],
        "2. TODOS LOS 20 ACTIVOS + GOLDEN RULES INTEGRADAS": [],
        "3. SOLO LOS 3 MAJORS (BTC, ETH, SOL) CON GOLDEN RULES": []
    }

    asset_performance = {}

    for symbol, file_path in downloaded_files:
        print(f"⚡ Auditando {symbol}...", flush=True)
        df = pd.read_parquet(file_path)
        df["ema200"] = df["close"].ewm(span=200, adjust=False).mean()
        df["ema800"] = df["close"].ewm(span=min(800, len(df)), adjust=False).mean()

        window_size = 100
        asset_pnls = []

        for i in range(window_size, len(df) - 96, 24):
            sub_df = df.iloc[i-window_size:i].copy().reset_index(drop=True)
            current_price = float(sub_df["close"].iloc[-1])
            ema200_val = float(sub_df["ema200"].iloc[-1])
            ema800_val = float(sub_df["ema800"].iloc[-1])
            ts = int(sub_df["timestamp"].iloc[-1])
            
            dt_utc = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
            day_name = dt_utc.strftime('%A')
            hour_utc = dt_utc.hour

            is_monday_pre_ny = (day_name == "Monday" and hour_utc < 13)
            
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

                if sl > 0 and tp1 > 0:
                    outcome, pnl = simulate_trade(df, i, direction, optimal_entry, sl, tp1, tp2, tp3)

                    # Escenario 1: Base en todos los 20
                    if score >= 50 and is_trend_ok:
                        scenarios["1. TODOS LOS 20 ACTIVOS (Confluencia >= 50% + EMA200 15m)"].append(pnl)

                    # Escenario 2: Golden Rules en todos los 20 (score >= 50, HTF aligned, no Monday pre-NY)
                    if score >= 50 and is_trend_ok and is_htf_aligned and not is_monday_pre_ny:
                        scenarios["2. TODOS LOS 20 ACTIVOS + GOLDEN RULES INTEGRADAS"].append(pnl)
                        asset_pnls.append(pnl)

                        # Escenario 3: Solo BTC, ETH, SOL
                        if symbol in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]:
                            scenarios["3. SOLO LOS 3 MAJORS (BTC, ETH, SOL) CON GOLDEN RULES"].append(pnl)

        asset_performance[symbol] = asset_pnls

    print("\n" + "=" * 95)
    print("📊 RESULTADOS COMPARATIVOS GLOBALES DE LOS 20 ACTIVOS VIP (6 MESES)")
    print("=" * 95)

    for sc_name, pnls in scenarios.items():
        total_t = len(pnls)
        if total_t == 0:
            print(f"\n❌ {sc_name}: 0 trades generados.")
            continue
        wins = sum(1 for p in pnls if p > 0)
        losses = sum(1 for p in pnls if p < 0)
        net_pnl = sum(pnls)
        win_rate = (wins / total_t * 100)
        pf = (wins * 200.0 / (losses * 100.0)) if losses > 0 else (99.0 if wins > 0 else 0.0)

        print(f"\n🚀 {sc_name}:")
        print(f"   • Total Trades Evaluados : {total_t}")
        print(f"   • Ganadoras / Perdedoras : {wins} / {losses}")
        print(f"   • Win Rate (Acierto)     : {win_rate:.2f}%")
        print(f"   • Beneficio Neto Realizado: ${net_pnl:+,.2f} USDT")
        print(f"   • Profit Factor Estándar : {pf:.2f}")

    print("\n" + "=" * 95)
    print("🏆 DESGLOSE DE RENDIMIENTO POR ACTIVO (TOP PRODUCTORES DE GANANCIA)")
    print("=" * 95)
    
    sorted_assets = sorted(asset_performance.items(), key=lambda item: sum(item[1]), reverse=True)
    for sym, pnls in sorted_assets:
        t_count = len(pnls)
        if t_count == 0:
            print(f"   • {sym:12s} : 0 trades")
            continue
        w = sum(1 for p in pnls if p > 0)
        l = sum(1 for p in pnls if p < 0)
        net = sum(pnls)
        wr = (w / t_count * 100) if t_count > 0 else 0
        print(f"   • {sym:12s} : {t_count:3d} trades | WR: {wr:5.1f}% | Net PnL: ${net:+8.2f} USDT | W/L: {w}/{l}")

    print("=" * 95)

if __name__ == "__main__":
    asyncio.run(audit_all_20_assets())
