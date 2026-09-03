import os
import time
import datetime
import urllib.request
import json
import pandas as pd

DATA_DIR = os.path.join("engine", "backtest", "data")
os.makedirs(DATA_DIR, exist_ok=True)

ASSETS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "LINKUSDT", "XRPUSDT"]
DAYS = 180  # 6 Meses

def fetch_klines_180d(symbol):
    print(f"📥 Descargando 6 meses (180 días) de datos de 15m para {symbol} desde Binance Futures...")
    
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (DAYS * 24 * 60 * 60 * 1000)
    
    all_klines = []
    current_start = start_ms
    
    headers = {"User-Agent": "Mozilla/5.0"}

    while current_start < now_ms:
        url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval=15m&limit=1500&startTime={current_start}"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if not data:
                    break
                all_klines.extend(data)
                last_ts = data[-1][0]
                if last_ts <= current_start:
                    break
                current_start = last_ts + 1
                time.sleep(0.05)  # Rate limiting suave
        except Exception as e:
            print(f"⚠️ Error descargando {symbol}: {e}")
            break

    if not all_klines:
        print(f"❌ No se pudieron obtener datos para {symbol}")
        return

    # Convertir a DataFrame estandarizado ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'taker_buy_volume']
    rows = []
    for k in all_klines:
        rows.append({
            "timestamp": int(k[0] // 1000),
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
            "taker_buy_volume": float(k[9])
        })
        
    df = pd.DataFrame(rows)
    # Eliminar duplicados si los hay
    df = df.drop_duplicates(subset=["timestamp"]).reset_index(drop=True)
    
    file_path = os.path.join(DATA_DIR, f"{symbol}_15m_180d.parquet")
    df.to_parquet(file_path)
    print(f"✅ {symbol}: {len(df):,} velas guardadas en {file_path}")

if __name__ == "__main__":
    print("=" * 80)
    print("🌐 DESCARGADOR DE DATOS HISTÓRICOS binance FUTURES — 6 MESES (180 DÍAS)")
    print("=" * 80)
    for asset in ASSETS:
        fetch_klines_180d(asset)
    print("=" * 80)
    print("🎉 Descarga de 6 meses completada con éxito.")
