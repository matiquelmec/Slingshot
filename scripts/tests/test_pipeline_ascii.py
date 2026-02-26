import sys, asyncio
sys.path.insert(0, '.')
import pandas as pd
import httpx

async def main():
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get('https://api.binance.com/api/v3/klines',
                        params={'symbol':'BTCUSDT','interval':'15m','limit':500})
        raw = r.json()
    df = pd.DataFrame(raw, columns=['timestamp','open','high','low','close','volume',
                                    'ct','qv','t','tbb','tbq','i'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    for col in ['open','high','low','close','volume']:
        df[col] = df[col].astype(float)
    print(f'DATA: {len(df)} velas, ultimo precio: {df.close.iloc[-1]:.2f}')

    from engine.indicators.regime import RegimeDetector
    df2 = RegimeDetector().detect_regime(df.copy())
    rc = df2['market_regime'].value_counts().to_dict()
    cr = df2['market_regime'].iloc[-1]
    print(f'REGIMEN ACTUAL: {cr}')
    print(f'DISTRIBUCION 500 velas: {rc}')

    from engine.main_router import SlingshotRouter
    result = SlingshotRouter().process_market_data(df.copy(), asset='BTCUSDT', interval='15m')
    print(f'ESTRATEGIA ACTIVA: {result["active_strategy"]}')
    print(f'SENALES EN VELA ACTUAL: {len(result["signals"])}')
    for s in result['signals']:
        print(f'  SENAL: {s.get("type")} a {s.get("price",0):.2f} trigger={s.get("trigger","")}')

    from engine.strategies.reversion import ReversionStrategy
    r1 = ReversionStrategy()
    opps1 = r1.find_opportunities(r1.analyze(df.copy()))
    print(f'ReversionStrategy hist: {len(opps1)} opp')
    if opps1:
        o = opps1[-1]
        print(f'  Ultima: {o["type"]} a {o["price"]:.2f}')

    from engine.strategies.trend import TrendFollowingStrategy
    r2 = TrendFollowingStrategy()
    opps2 = r2.find_opportunities(r2.analyze(df.copy()))
    print(f'TrendFollowingStrategy hist: {len(opps2)} opp')
    if opps2:
        o = opps2[-1]
        print(f'  Ultima: {o["type"]} a {o["price"]:.2f}')

    from engine.strategies.smc import PaulPerdicesStrategy
    r3 = PaulPerdicesStrategy()
    opps3 = r3.find_opportunities(r3.analyze(df.copy()))
    print(f'PaulPerdicesSMC hist: {len(opps3)} opp')
    if opps3:
        o = opps3[-1]
        print(f'  Ultima: {o["type"]} a {o["price"]:.2f}')

    from engine.indicators.ghost_data import refresh_ghost_data
    g = await refresh_ghost_data('BTCUSDT')
    print(f'GHOST: F&G={g.fear_greed_value} ({g.fear_greed_label}), BTCD={g.btc_dominance}%, Funding={g.funding_rate:.4f}%, Bias={g.macro_bias}')
    print(f'GHOST: BlockLONGs={g.block_longs}, BlockSHORTs={g.block_shorts}')
    print('PIPELINE COMPLETO OK')

asyncio.run(main())
