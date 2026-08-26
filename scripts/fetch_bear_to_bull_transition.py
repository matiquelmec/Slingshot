"""
scripts/fetch_bear_to_bull_transition.py
=============================================================================
Descargador de datos históricos para la transición exacta Bear Market -> Bull Market
Periodo: 01 de Diciembre de 2022 al 30 de Mayo de 2023 (Fondo $16k -> Rally $31k)
=============================================================================
"""

import httpx
import pandas as pd
import asyncio
import os
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), "../engine/backtest/data")
os.makedirs(DATA_DIR, exist_ok=True)

# Activos clave para la transición
TARGET_ASSETS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "AVAXUSDT", "NEARUSDT", "INJUSDT", "FETUSDT"]

# Rango de fechas: 01-Dic-2022 (Fondo de Pánico FTX $16k) al 01-Jun-2023 (Despegue a $31k)
START_DATE = "2022-12-01"
END_DATE = "2023-06-01"

START_TS = int(datetime.strptime(START_DATE, "%Y-%m-%d").timestamp() * 1000)
END_TS = int(datetime.strptime(END_DATE, "%Y-%m-%d").timestamp() * 1000)

async def fetch_klines(client: httpx.AsyncClient, symbol: str, start_ts: int, end_ts: int, interval: str = "15m"):
    url = "https://api.binance.com/api/v3/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "startTime": start_ts,
        "endTime": end_ts,
        "limit": 1000
    }
    for attempt in range(3):
        try:
            res = await client.get(url, params=params, timeout=15.0)
            if res.status_code == 200:
                return res.json()
            await asyncio.sleep(0.2)
        except Exception:
            await asyncio.sleep(0.3)
    return []

async def download_asset_history(symbol: str):
    print(f"📥 Descargando transición Bear->Bull para {symbol} (15m)...")
    all_klines = []
    current_start = START_TS
    
    async with httpx.AsyncClient(limits=httpx.Limits(max_keepalive_connections=20, max_connections=50)) as client:
        while current_start < END_TS:
            klines = await fetch_klines(client, symbol, current_start, END_TS, interval="15m")
            if not klines:
                break
            all_klines.extend(klines)
            current_start = klines[-1][6] + 1
            await asyncio.sleep(0.05)
            
    if not all_klines:
        print(f"⚠️ No se pudieron obtener datos para {symbol}")
        return
        
    df = pd.DataFrame(all_klines, columns=['t', 'o', 'h', 'l', 'c', 'v', 'T', 'q', 'n', 'V', 'Q', 'B'])
    df_clean = pd.DataFrame({
        'timestamp': (df['t'] / 1000).astype(int),
        'open': df['o'].astype(float),
        'high': df['h'].astype(float),
        'low': df['l'].astype(float),
        'close': df['c'].astype(float),
        'volume': df['v'].astype(float)
    })
    
    out_file = os.path.join(DATA_DIR, f"{symbol}_15m_bear2bull_2023.parquet")
    df_clean.to_parquet(out_file, index=False)
    print(f"✅ {symbol} guardado: {len(df_clean)} velas en {os.path.basename(out_file)}")

async def main():
    print("="*75)
    print(f"🌍 DESCARGANDO DATOS HISTÓRICOS: TRANSICIÓN BEAR MARKET -> BULL RUN (2023)")
    print(f"📅 Rango: {START_DATE} a {END_DATE} (Fondo FTX $16k -> Expansión $31k)")
    print("="*75)
    tasks = [download_asset_history(sym) for sym in TARGET_ASSETS]
    await asyncio.gather(*tasks)
    print("="*75)
    print("🚀 Descarga completada. Listo para auditar.")

if __name__ == "__main__":
    asyncio.run(main())
