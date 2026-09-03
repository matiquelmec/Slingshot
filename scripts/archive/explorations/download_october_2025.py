import httpx
import pandas as pd
import datetime
import time
import os

ASSETS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]
INTERVAL = "15m"
DATA_DIR = os.path.join("engine", "backtest", "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Oct 1, 2025 00:00:00 UTC to Oct 31, 2025 23:59:59 UTC
start_ms = int(datetime.datetime(2025, 10, 1, 0, 0, 0, tzinfo=datetime.timezone.utc).timestamp() * 1000)
end_ms = int(datetime.datetime(2025, 10, 31, 23, 59, 59, tzinfo=datetime.timezone.utc).timestamp() * 1000)

def fetch_full_range(symbol: str, interval: str, start_time: int, end_time: int):
    print(f"📥 Descargando {symbol} ({interval}) para Octubre 2025...")
    all_candles = []
    current_start = start_time

    while current_start < end_time:
        url = "https://fapi.binance.com/fapi/v1/klines"
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": current_start,
            "endTime": end_time,
            "limit": 1500
        }
        res = httpx.get(url, params=params, timeout=10.0)
        if res.status_code != 200:
            print(f"❌ Error HTTP {res.status_code}: {res.text}")
            break
        
        data = res.json()
        if not data:
            break
        
        all_candles.extend(data)
        last_candle_time = data[-1][0]
        if last_candle_time <= current_start:
            break
        current_start = last_candle_time + 1
        time.sleep(0.1)

    print(f"✅ {symbol}: {len(all_candles)} velas descargadas.")
    
    # Formatear DataFrame
    cols = ["timestamp", "open", "high", "low", "close", "volume", "close_time", 
            "quote_volume", "trades", "taker_buy_volume", "taker_buy_quote_volume", "ignore"]
    df = pd.DataFrame(all_candles, columns=cols)
    numeric_cols = ["open", "high", "low", "close", "volume", "quote_volume", "taker_buy_volume"]
    for col in numeric_cols:
        df[col] = df[col].astype(float)
    
    df["timestamp"] = df["timestamp"].astype(int) // 1000  # Convertir a segundos UNIX
    output_path = os.path.join(DATA_DIR, f"{symbol}_15m_oct2025.parquet")
    df.to_parquet(output_path, index=False)
    print(f"💾 Guardado en: {output_path}")
    return df

if __name__ == "__main__":
    for asset in ASSETS:
        fetch_full_range(asset, INTERVAL, start_ms, end_ms)
