# scripts/historical_fetcher.py
import httpx
import pandas as pd
import asyncio
import os
from datetime import datetime, timedelta

# Configuración Institucional
TARGET_ASSETS = ["BTCUSDT", "SOLUSDT", "ETHUSDT"]
INTERVAL = "1m"
DAYS_TO_FETCH = 30
DATA_DIR = os.path.join(os.path.dirname(__file__), "../engine/tests/data")

async def fetch_binance_klines(symbol: str, start_ts: int, end_ts: int, limit: int = 1000):
    """Extrae velas históricas de Binance vía REST API."""
    url = "https://api.binance.com/api/v3/klines"
    params = {
        "symbol": symbol,
        "interval": INTERVAL,
        "startTime": start_ts,
        "endTime": end_ts,
        "limit": limit
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params, timeout=15.0)
        response.raise_for_status()
        return response.json()

async def build_historical_dataset(symbol: str):
    """Construye un DataFrame continuo manejando la paginación de Binance."""
    print(f"[FETCHER] Iniciando extraccion para {symbol} ({DAYS_TO_FETCH} dias)...")
    
    end_time = int(datetime.now().timestamp() * 1000)
    start_time = int((datetime.now() - timedelta(days=DAYS_TO_FETCH)).timestamp() * 1000)
    
    all_klines = []
    current_start = start_time
    
    while current_start < end_time:
        try:
            klines = await fetch_binance_klines(symbol, current_start, end_time)
            if not klines:
                break
            
            all_klines.extend(klines)
            # El timestamp de cierre del último elemento + 1ms para la siguiente página
            current_start = klines[-1][6] + 1 
            
            # Rate limit safety (evitar ban de IP institucional)
            await asyncio.sleep(0.1) 
        except Exception as e:
            print(f"[ERROR] Extrayendo {symbol}: {e}")
            break

    if not all_klines:
        print(f"[WARNING] No se obtuvieron datos para {symbol}")
        return

    # Formateo a DataFrame Delta
    cols = ['t', 'o', 'h', 'l', 'c', 'v', 'close_time', 'qav', 'num_trades', 'taker_base_vol', 'taker_quote_vol', 'ignore']
    df = pd.DataFrame(all_klines, columns=cols)
    
    # Casting estricto para el Engine
    for col in ['o', 'h', 'l', 'c', 'v']:
        df[col] = df[col].astype(float)
    df['t'] = (df['t'].astype(int) // 1000) # Convertir a segundos para Slingshot
    
    # Guardar en bóveda
    os.makedirs(DATA_DIR, exist_ok=True)
    file_path = os.path.join(DATA_DIR, f"{symbol}_{INTERVAL}_{DAYS_TO_FETCH}d.parquet")
    df[['t', 'o', 'h', 'l', 'c', 'v']].to_parquet(file_path, index=False)
    
    print(f"[FETCHER] {symbol} completado: {len(df)} velas guardadas en {file_path}")

async def main():
    tasks = [build_historical_dataset(symbol) for symbol in TARGET_ASSETS]
    await asyncio.gather(*tasks)
    print("[OPERACION DATASET] Extraccion historica finalizada.")

if __name__ == "__main__":
    asyncio.run(main())
