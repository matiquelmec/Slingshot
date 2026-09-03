import os
import json
import time
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

def fetch_klines(symbol: str, timeframe: str = "4h", limit: int = 180):
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={timeframe}&limit={limit}"
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

def run_real_30d_audit():
    lines = []
    lines.append("=" * 90)
    lines.append("🦅 AUDITORÍA ESTRUCTURAL DE 30 DÍAS (Julio 8 - Agosto 8, 2026)")
    lines.append("=" * 90)
    
    btc_df = fetch_klines("BTCUSDT", timeframe="4h", limit=180)
    if btc_df is None or len(btc_df) < 50:
        lines.append("❌ No se pudieron descargar datos de BTC.")
        with open("scratch/report_30d_4h.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return

    btc_df["ema200"] = btc_df["close"].ewm(span=50, adjust=False).mean()
    
    asset_dfs = {"BTCUSDT": btc_df}
    for symbol in VIP_ASSETS:
        if symbol == "BTCUSDT":
            continue
        df = fetch_klines(symbol, timeframe="4h", limit=180)
        if df is not None and len(df) >= 50:
            df["ema200"] = df["close"].ewm(span=50, adjust=False).mean()
            asset_dfs[symbol] = df

    confluence = ConfluenceManager()
    signals_30d = []

    for idx in range(30, len(btc_df)):
        current_btc_close = btc_df["close"].iloc[idx]
        current_btc_ema = btc_df["ema200"].iloc[idx]
        timestamp = btc_df["timestamp"].iloc[idx]
        
        btc_macro_trend = "LONG" if current_btc_close > current_btc_ema else "SHORT"

        for symbol, df in asset_dfs.items():
            if idx >= len(df):
                continue
            
            sub_df = df.iloc[:idx+1].copy()
            current_price = sub_df["close"].iloc[-1]
            
            period_ker = 14
            change_ker = abs(float(sub_df['close'].iloc[-1]) - float(sub_df['close'].iloc[-period_ker]))
            volatility_ker = float(sub_df['close'].diff().abs().tail(period_ker).sum())
            ker_val = float(change_ker / volatility_ker) if volatility_ker > 0 else 0.5
            is_quarantined = ker_val < 0.22

            for direction in ["LONG", "SHORT"]:
                btc_aligned = (direction == btc_macro_trend)
                
                high_val = sub_df["high"].iloc[-10:].max()
                low_val = sub_df["low"].iloc[-10:].min()
                range_span = high_val - low_val
                
                if range_span <= 0:
                    continue

                if direction == "LONG" and current_price <= (low_val + range_span * 0.35):
                    poi_type = "ORDER_BLOCK_LONG"
                    bias = "BULLISH"
                elif direction == "SHORT" and current_price >= (high_val - range_span * 0.35):
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

                if conviction == "VETADA" or score < 50:
                    continue

                HIGH_NOISE_ASSETS = ['BNBUSDT', 'XRPUSDT', 'SOLUSDT', 'LINKUSDT']
                if (is_quarantined or symbol in HIGH_NOISE_ASSETS) and score < 65:
                    continue

                recent_triggers = [s for s in signals_30d if s["asset"] == symbol and s["direction"] == direction]
                if recent_triggers:
                    last_trigger_time = datetime.strptime(recent_triggers[-1]["timestamp"], "%Y-%m-%d %H:%M")
                    if (timestamp - last_trigger_time).total_seconds() < 86400:
                        continue

                sl_pct = 0.025
                tp1_pct = 0.025
                tp3_pct = 0.075

                future_df = df.iloc[idx+1 : idx+15]
                outcome = "OPEN"
                pnl_r = 0.0

                if direction == "LONG":
                    sl_price = current_price * (1.0 - sl_pct)
                    tp1_price = current_price * (1.0 + tp1_pct)
                    tp3_price = current_price * (1.0 + tp3_pct)

                    for _, f_row in future_df.iterrows():
                        if f_row["low"] <= sl_price:
                            outcome = "STOP_LOSS"
                            pnl_r = -1.0
                            break
                        if f_row["high"] >= tp3_price:
                            outcome = "TP3_TARGET"
                            pnl_r = 3.0
                            break
                        if f_row["high"] >= tp1_price and outcome == "OPEN":
                            outcome = "TP1_BREAKEVEN"
                            pnl_r = 1.0
                else:
                    sl_price = current_price * (1.0 + sl_pct)
                    tp1_price = current_price * (1.0 - tp1_pct)
                    tp3_price = current_price * (1.0 - tp3_pct)

                    for _, f_row in future_df.iterrows():
                        if f_row["high"] >= sl_price:
                            outcome = "STOP_LOSS"
                            pnl_r = -1.0
                            break
                        if f_row["low"] <= tp3_price:
                            outcome = "TP3_TARGET"
                            pnl_r = 3.0
                            break
                        if f_row["low"] <= tp1_price and outcome == "OPEN":
                            outcome = "TP1_BREAKEVEN"
                            pnl_r = 1.0

                if outcome == "OPEN":
                    outcome = "BREAKEVEN"
                    pnl_r = 0.0

                signals_30d.append({
                    "timestamp": timestamp.strftime("%Y-%m-%d %H:%M"),
                    "asset": symbol,
                    "direction": direction,
                    "score": score,
                    "conviction": conviction,
                    "price": round(current_price, 4),
                    "outcome": outcome,
                    "pnl_r": pnl_r,
                    "ker": round(ker_val, 2)
                })

    lines.append("\n" + "=" * 90)
    lines.append("📊 RESULTADOS DEL BACKTEST DE LOS ÚLTIMOS 30 DÍAS (4h Klines)")
    lines.append("=" * 90)

    if not signals_30d:
        lines.append("ℹ️ No se registraron señales en los últimos 30 días.")
    else:
        df_res = pd.DataFrame(signals_30d)
        total_trades = len(df_res)
        wins = len(df_res[df_res["pnl_r"] > 0])
        losses = len(df_res[df_res["pnl_r"] < 0])
        breakevens = len(df_res[df_res["pnl_r"] == 0])

        win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0
        total_r = df_res["pnl_r"].sum()

        lines.append(f"🔹 Total de Señales Validadas en 30 Días: {total_trades}")
        lines.append(f"✅ Ganadoras (TP1/TP3): {wins} | ❌ Perdedoras (SL): {losses} | ⚖️ Breakeven: {breakevens}")
        lines.append(f"🎯 Win Rate: {win_rate:.1f}%")
        lines.append(f"💰 PnL Total en Unidades de Riesgo (R): +{total_r:.1f} R")
        lines.append(f"💵 Beneficio estimado en cuenta de $1,000 USD (2% Riesgo / $20 por trade): +${total_r * 20:.2f} USD (+{total_r * 2.0:.1f}%)")
        lines.append("-" * 90)
        lines.append("\n📋 OPERACIONES REGISTRADAS EN LOS ÚLTIMOS 30 DÍAS:")
        lines.append(df_res[["timestamp", "asset", "direction", "score", "conviction", "outcome", "pnl_r"]].to_string(index=False))

    txt_content = "\n".join(lines)
    print(txt_content)
    with open("scratch/report_30d_4h.txt", "w", encoding="utf-8") as f:
        f.write(txt_content)

if __name__ == "__main__":
    run_real_30d_audit()
