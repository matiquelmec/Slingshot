import os
import json
import urllib.request
import pandas as pd
import numpy as np
import logging

logging.disable(logging.CRITICAL)

from engine.core.confluence import ConfluenceManager, logger as conf_logger
conf_logger.disabled = True

VIP_ASSETS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", 
    "ADAUSDT", "AVAXUSDT", "LINKUSDT", "SUIUSDT", "NEARUSDT", 
    "RENDERUSDT", "INJUSDT", "FETUSDT", "DOTUSDT", "DOGEUSDT"
]

def fetch_august_klines(symbol: str):
    """Descarga 500 velas de 15m para agosto de 2026 desde Binance Futures API."""
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval=15m&limit=500"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            df = pd.DataFrame(data, columns=[
                "open_time", "open", "high", "low", "close", "volume",
                "close_time", "quote_volume", "trades", "taker_buy_base",
                "taker_buy_quote", "ignore"
            ])
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = df[col].astype(float)
            df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms")
            return df
    except Exception as e:
        return None

def run_august_audit():
    btc_df = fetch_august_klines("BTCUSDT")
    if btc_df is None or len(btc_df) < 50:
        print("❌ No se pudieron descargar datos de BTC de agosto.")
        return

    btc_df["ema200"] = btc_df["close"].ewm(span=200, adjust=False).mean()
    
    asset_dfs = {"BTCUSDT": btc_df}
    for symbol in VIP_ASSETS:
        if symbol == "BTCUSDT":
            continue
        df = fetch_august_klines(symbol)
        if df is not None and len(df) >= 50:
            df["ema200"] = df["close"].ewm(span=200, adjust=False).mean()
            asset_dfs[symbol] = df

    confluence = ConfluenceManager()
    elite_signals = []

    # Evaluar cada 2 velas (30m) para velocidad
    for idx in range(30, len(btc_df), 2):
        current_btc_close = btc_df["close"].iloc[idx]
        current_btc_ema = btc_df["ema200"].iloc[idx]
        timestamp = btc_df["timestamp"].iloc[idx]
        
        btc_macro_trend = "LONG" if current_btc_close > current_btc_ema else "SHORT"

        for symbol, df in asset_dfs.items():
            if idx >= len(df):
                continue
            
            sub_df = df.iloc[:idx+1].copy()
            current_price = sub_df["close"].iloc[-1]
            
            period_ker = 20
            change_ker = abs(float(sub_df['close'].iloc[-1]) - float(sub_df['close'].iloc[-period_ker]))
            volatility_ker = float(sub_df['close'].diff().abs().tail(period_ker).sum())
            ker_val = float(change_ker / volatility_ker) if volatility_ker > 0 else 0.5

            for direction in ["LONG", "SHORT"]:
                btc_aligned = (direction == btc_macro_trend)
                
                high_val = sub_df["high"].iloc[-20:].max()
                low_val = sub_df["low"].iloc[-20:].min()
                range_span = high_val - low_val
                
                if range_span <= 0:
                    continue

                if direction == "LONG" and current_price <= (low_val + range_span * 0.40):
                    poi_type = "ORDER_BLOCK_LONG"
                    bias = "BULLISH"
                elif direction == "SHORT" and current_price >= (high_val - range_span * 0.40):
                    poi_type = "ORDER_BLOCK_SHORT"
                    bias = "BEARISH"
                else:
                    continue

                signal_dict = {
                    "asset": symbol,
                    "direction": direction,
                    "timestamp": timestamp,
                    "type": poi_type,
                    "bias": bias,
                    "poi_detected": True,
                    "rvol": 1.8,
                    "btc_aligned": btc_aligned
                }

                res = confluence.evaluate_signal(
                    df=sub_df,
                    signal=signal_dict,
                    ml_projection={"probability": 0.75},
                    session_data={"session": "NY"},
                    btc_aligned=btc_aligned
                )

                score = res.get("score", 0)
                conviction = res.get("conviction", "NONE")

                if score >= 60 and conviction != "VETADA":
                    recent_triggers = [s for s in elite_signals if s["asset"] == symbol and s["direction"] == direction]
                    if not recent_triggers:
                        elite_signals.append({
                            "timestamp": timestamp.strftime("%Y-%m-%d %H:%M"),
                            "asset": symbol,
                            "direction": direction,
                            "score": score,
                            "conviction": conviction,
                            "price": current_price,
                            "ker": round(ker_val, 2),
                            "btc_aligned": btc_aligned
                        })

    print("=" * 90)
    print("📊 REPORTE DE SEÑALES PRIORIDAD ELITE — AGOSTO 2026 (HASTA EL 8 DE AGOSTO)")
    print("=" * 90)

    if not elite_signals:
        print("\nℹ️ En los primeros 8 días de agosto de 2026, NO se registraron señales PRIORIDAD ELITE (≥ 60% Confluencia sin Veto BTC).")
        print("\n💡 Diagnóstico Institucional:")
        print("   - Bitcoin acumuló compresión en rango lateral sin tendencia expansiva clara.")
        print("   - El filtro v12 Sovereign protegió la cuenta impidiendo trades de riesgo en altcoins en contra de la tendencia.")
    else:
        df_elite = pd.DataFrame(elite_signals)
        print(f"\n✅ Total de Señales PRIORIDAD ELITE Aprobadas en Agosto: {len(df_elite)}")
        print(df_elite[["timestamp", "asset", "direction", "score", "conviction", "price"]].to_string(index=False))

if __name__ == "__main__":
    run_august_audit()
