import pandas as pd
from engine.indicators.regime import RegimeDetector
import httpx
import asyncio

async def main():
    url = 'https://api.binance.com/api/v3/klines'
    params = {'symbol': 'BTCUSDT', 'interval': '15m', 'limit': 500}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        raw = response.json()
    candles = []
    for k in raw:
        candles.append({
            'timestamp': k[0]/1000, 'open': float(k[1]), 'high': float(k[2]),
            'low': float(k[3]), 'close': float(k[4]), 'volume': float(k[5])
        })
    df = pd.DataFrame(candles)
    detector = RegimeDetector()
    df_regime = detector.detect_regime(df)
    last_regime = df_regime.iloc[-1]
    print(f'market_regime: {last_regime["market_regime"]}')

    print(f'\nLast 10 Regimes: {df_regime["market_regime"].tail(10).tolist()}')

if __name__ == "__main__":
    asyncio.run(main())
