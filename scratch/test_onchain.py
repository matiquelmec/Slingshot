
import asyncio
import sys
import os

# Añadir el directorio raíz al path para poder importar los módulos
sys.path.append(os.getcwd())

from engine.indicators.onchain_provider import refresh_symbol_onchain, get_onchain_summary, _cache
from engine.core.logger import logger

async def test_onchain():
    symbol = "BTCUSDT"
    print(f"--- Testing OnChain for {symbol} ---")
    
    # 1. Primer refresco (debería dar Delta 0)
    print("Initial refresh...")
    await refresh_symbol_onchain(symbol)
    summary = get_onchain_summary(symbol)
    print(f"Summary 1: {summary}")
    
    # 2. Esperar un poco y refrescar de nuevo (OI debería haber cambiado algo)
    print("Waiting 10s for market change...")
    await asyncio.sleep(10)
    
    print("Second refresh...")
    await refresh_symbol_onchain(symbol)
    summary = get_onchain_summary(symbol)
    print(f"Summary 2: {summary}")
    
    if summary['oi_delta_pct'] == 0:
        print("Warning: Delta still 0. This might be normal if OI hasn't moved, or suspicious if it's exactly 0.000000.")
    else:
        print(f"Success: Delta changed to {summary['oi_delta_pct']}%")

if __name__ == "__main__":
    asyncio.run(test_onchain())
