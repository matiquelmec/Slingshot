import asyncio
import pandas as pd
import httpx
from engine.main_router import SlingshotRouter

async def test_symbol(symbol):
    print(f"\n--- Testing {symbol} ---")
    url = f"https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": "15m", "limit": 1000}
    async with httpx.AsyncClient() as client:
        r = await client.get(url, params=params)
        raw = r.json()
    
    df = pd.DataFrame(raw, columns=['t','o','h','l','c','v','ct','qv','tr','tbb','tbq','i'])
    df['timestamp'] = pd.to_datetime(df['t'], unit='ms')
    for col in ['o','h','l','c','v']: df[col] = df[col].astype(float)
    df = df.rename(columns={'t':'time','o':'open','h':'high','l':'low','c':'close','v':'volume'})

    router = SlingshotRouter()
    # Mocking some data for the router if needed
    result = router.process_market_data(df, asset=symbol, interval="15m")
    
    print(f"Regime: {result['market_regime']}")
    print(f"Strategy: {result['active_strategy']}")
    print(f"Signals in result: {len(result['signals'])}")
    
    # Check internal strategy counts
    from engine.strategies.reversion import ReversionStrategy
    from engine.strategies.trend import TrendFollowingStrategy
    from engine.strategies.smc import PaulPerdicesStrategy
    
    rev = ReversionStrategy()
    trend = TrendFollowingStrategy()
    smc = PaulPerdicesStrategy()
    
    print(f"Historical counts (1000 candles):")
    print(f"  Reversion: {len(rev.find_opportunities(rev.analyze(df.copy())))}")
    print(f"  Trend:     {len(trend.find_opportunities(trend.analyze(df.copy())))}")
    print(f"  SMC:       {len(smc.find_opportunities(smc.analyze(df.copy())))}")

async def run():
    for s in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]:
        await test_symbol(s)

if __name__ == "__main__":
    asyncio.run(run())
