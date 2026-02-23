"""
Test End-to-End del pipeline completo de Slingshot.
Descarga datos reales de Binance, corre el router y verifica señales.
"""
import sys
sys.path.insert(0, '.')

import asyncio
import pandas as pd
import httpx
from datetime import datetime

async def fetch_real_data(symbol="BTCUSDT", interval="15m", limit=500):
    """Descarga velas reales de Binance."""
    url = f"https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        raw = r.json()
    
    df = pd.DataFrame(raw, columns=[
        'timestamp','open','high','low','close','volume',
        'close_time','quote_vol','trades','taker_buy_base',
        'taker_buy_quote','ignore'
    ])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    for col in ['open','high','low','close','volume']:
        df[col] = df[col].astype(float)
    return df

async def main():
    print("="*60)
    print("🔬 TEST END-TO-END PIPELINE SLINGSHOT v1.0")
    print(f"⏱  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (hora local)")
    print("="*60)

    # 1. Descargar datos reales
    print("\n📡 Descargando 500 velas BTCUSDT 15m desde Binance...")
    df = await fetch_real_data("BTCUSDT", "15m", 500)
    print(f"✅ {len(df)} velas recibidas. Última vela: {df['timestamp'].iloc[-1]}")
    print(f"   Último precio: ${df['close'].iloc[-1]:,.2f}")

    # 2. Correr el RegimeDetector directamente
    print("\n🔮 Detectando régimen de mercado (Wyckoff)...")
    from engine.indicators.regime import RegimeDetector
    detector = RegimeDetector()
    df_regime = detector.detect_regime(df.copy())
    regime_counts = df_regime['market_regime'].value_counts()
    current_regime = df_regime['market_regime'].iloc[-1]
    print(f"✅ Régimen ACTUAL (última vela): {current_regime}")
    print(f"   Distribución últimas 500 velas: {dict(regime_counts)}")

    # 3. Correr el SlingshotRouter completo
    print("\n🧠 Corriendo SlingshotRouter completo...")
    from engine.main_router import SlingshotRouter
    router = SlingshotRouter()
    result = router.process_market_data(df.copy(), asset="BTCUSDT", interval="15m")
    
    print(f"✅ Estrategia activa: {result['active_strategy']}")
    print(f"   Régimen: {result['market_regime']}")
    print(f"   Señales generadas: {len(result['signals'])}")
    
    if result['signals']:
        for s in result['signals']:
            print(f"   🎯 {s.get('type')} @ ${s.get('price', 0):,.2f} | Trigger: {s.get('trigger', 'N/A')}")
    else:
        print("   ℹ️  Sin señales en la vela actual (normal si no hay confluencia)")

    # 4. Test individual de cada estrategia
    print("\n📊 Test individual de estrategias...")
    
    # ReversionStrategy
    from engine.strategies.reversion import ReversionStrategy
    rev = ReversionStrategy()
    df_rev = rev.analyze(df.copy())
    opps_rev = rev.find_opportunities(df_rev)
    print(f"   ReversionStrategy: {len(opps_rev)} oportunidades en historial")
    if opps_rev:
        last = opps_rev[-1]
        print(f"     Última: {last.get('type')} @ ${last.get('price', 0):,.2f} | {last.get('trigger')}")
    
    # TrendFollowingStrategy
    from engine.strategies.trend import TrendFollowingStrategy
    trend = TrendFollowingStrategy()
    df_trend = trend.analyze(df.copy())
    opps_trend = trend.find_opportunities(df_trend)
    print(f"   TrendFollowingStrategy: {len(opps_trend)} oportunidades en historial")
    if opps_trend:
        last = opps_trend[-1]
        print(f"     Última: {last.get('type')} @ ${last.get('price', 0):,.2f} | {last.get('trigger')}")

    # PaulPerdicesStrategy (SMC)
    from engine.strategies.smc import PaulPerdicesStrategy
    smc = PaulPerdicesStrategy()
    df_smc = smc.analyze(df.copy())
    opps_smc = smc.find_opportunities(df_smc)
    print(f"   PaulPerdicesSMC: {len(opps_smc)} oportunidades en historial")
    if opps_smc:
        last = opps_smc[-1]
        print(f"     Última: {last.get('type')} @ ${last.get('price', 0):,.2f} | {last.get('trigger')}")

    # 5. Ghost Data (contexto macro real)
    print("\n🔮 Contexto macro actual (Ghost Data)...")
    from engine.indicators.ghost_data import refresh_ghost_data
    ghost = await refresh_ghost_data("BTCUSDT")
    print(f"   Fear & Greed: {ghost.fear_greed_value} ({ghost.fear_greed_label})")
    print(f"   BTC Dominance: {ghost.btc_dominance}%")
    print(f"   Funding Rate: {ghost.funding_rate:.4f}%")
    print(f"   Macro Bias: {ghost.macro_bias}")
    print(f"   Block LONGs: {ghost.block_longs} | Block SHORTs: {ghost.block_shorts}")

    print("\n" + "="*60)
    print("✅ TEST COMPLETADO")
    print("="*60)

asyncio.run(main())
