import os
import json
import sys
import time
import urllib.request
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Desactivar loggers
import logging
logging.disable(logging.CRITICAL)

from engine.core.confluence import ConfluenceManager

VIP_ASSETS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", 
    "ADAUSDT", "AVAXUSDT", "LINKUSDT", "SUIUSDT", "NEARUSDT", 
    "RENDERUSDT", "INJUSDT", "FETUSDT", "DOTUSDT", "DOGEUSDT"
]

def fetch_klines(symbol: str, interval: str = "15m", limit: int = 672):
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
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

def run():
    lines = []
    lines.append("=" * 90)
    lines.append("🦅 SLINGSHOT v12 SOVEREIGN CORE — BACKTEST EN VIVO (ÚLTIMOS 7 DÍAS)")
    lines.append("=" * 90)
    
    btc_df = fetch_klines("BTCUSDT", interval="15m", limit=672)
    if btc_df is None or len(btc_df) < 200:
        lines.append("❌ No se pudo descargar BTCUSDT.")
        with open("scratch/backtest_report_7d.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return

    btc_df["ema200"] = btc_df["close"].ewm(span=200, adjust=False).mean()
    
    asset_dfs = {"BTCUSDT": btc_df}
    for symbol in VIP_ASSETS:
        if symbol == "BTCUSDT":
            continue
        df = fetch_klines(symbol, interval="15m", limit=672)
        if df is not None and len(df) >= 200:
            df["ema200"] = df["close"].ewm(span=200, adjust=False).mean()
            asset_dfs[symbol] = df

    confluence = ConfluenceManager()
    all_signals = []

    for idx in range(200, len(btc_df), 2):
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
            is_quarantined = ker_val < 0.22

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
                    ml_projection={"probability": 0.72},
                    session_data={"session": "NY"},
                    btc_aligned=btc_aligned
                )

                score = res.get("score", 0)
                conviction = res.get("conviction", "NONE")

                if conviction == "VETADA" or score < 45:
                    continue

                HIGH_NOISE_ASSETS = ['BNBUSDT', 'XRPUSDT', 'SOLUSDT', 'LINKUSDT']
                if (is_quarantined or symbol in HIGH_NOISE_ASSETS) and score < 65:
                    continue

                recent_triggers = [s for s in all_signals if s["asset"] == symbol and s["direction"] == direction]
                if recent_triggers:
                    last_trigger_time = datetime.strptime(recent_triggers[-1]["timestamp"], "%Y-%m-%d %H:%M")
                    if (timestamp - last_trigger_time).total_seconds() < 14400:
                        continue

                sl_pct = 0.018
                tp1_pct = 0.018
                tp3_pct = 0.054

                future_df = df.iloc[idx+1 : idx+33]
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

                all_signals.append({
                    "timestamp": timestamp.strftime("%Y-%m-%d %H:%M"),
                    "asset": symbol,
                    "direction": direction,
                    "score": score,
                    "conviction": conviction,
                    "price": current_price,
                    "outcome": outcome,
                    "pnl_r": pnl_r,
                    "ker": round(ker_val, 2),
                    "btc_aligned": btc_aligned
                })

    lines.append("\n" + "=" * 90)
    lines.append("📊 RESULTADOS DEL BACKTEST DE LA ÚLTIMA SEMANA (v12 Sovereign Engine)")
    lines.append("=" * 90)

    if not all_signals:
        lines.append("ℹ️ No se registraron señales que superaran la confluencia y los filtros de veto en la última semana.")
    else:
        df_res = pd.DataFrame(all_signals)
        total_trades = len(df_res)
        wins = len(df_res[df_res["pnl_r"] > 0])
        losses = len(df_res[df_res["pnl_r"] < 0])
        breakevens = len(df_res[df_res["pnl_r"] == 0])

        win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0
        total_r = df_res["pnl_r"].sum()
        
        gross_profit = df_res[df_res["pnl_r"] > 0]["pnl_r"].sum() * 20.0
        gross_loss = abs(df_res[df_res["pnl_r"] < 0]["pnl_r"].sum()) * 20.0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 99.0

        lines.append(f"🔹 Total de Señales Validadas: {total_trades}")
        lines.append(f"✅ Ganadoras (TP1/TP3): {wins} | ❌ Perdedoras (SL): {losses} | ⚖️ Breakeven: {breakevens}")
        lines.append(f"🎯 Win Rate: {win_rate:.1f}%")
        lines.append(f"📈 Profit Factor: {profit_factor:.2f}")
        lines.append(f"💰 PnL Total en Unidades de Riesgo (R): +{total_r:.1f} R")
        lines.append(f"💵 Beneficio estimado en cuenta de $1,000 USD (2% Riesgo / $20 por trade): +${total_r * 20:.2f} USD (+{total_r * 2.0:.1f}%)")
        lines.append("-" * 90)
        lines.append("\n📋 LISTADO DE OPERACIONES DISPARADAS EN LA ÚLTIMA SEMANA:")
        lines.append(df_res[["timestamp", "asset", "direction", "score", "conviction", "outcome", "pnl_r"]].to_string(index=False))

    output_text = "\n".join(lines)
    print(output_text)
    with open("scratch/backtest_report_7d.txt", "w", encoding="utf-8") as f:
        f.write(output_text)

if __name__ == "__main__":
    run()
