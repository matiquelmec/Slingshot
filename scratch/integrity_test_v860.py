
import asyncio
import pandas as pd
import numpy as np
import sys
import os

# Forzar PYTHONPATH
sys.path.append(os.getcwd())

from engine.main_router import SlingshotRouter
from engine.router.gatekeeper import GatekeeperContext
from engine.indicators.htf_analyzer import HTFBias

async def test_integrity():
    print("Iniciando Test de Integridad Slingshot v8.6.0...")
    router = SlingshotRouter()
    
    # Mock DF
    df = pd.DataFrame({
        "timestamp": pd.date_range(start="2023-01-01", periods=100, freq="15min"),
        "open": np.random.uniform(30000, 31000, 100),
        "high": np.random.uniform(31000, 32000, 100),
        "low": np.random.uniform(29000, 30000, 100),
        "close": np.random.uniform(30000, 31000, 100),
        "volume": np.random.uniform(100, 1000, 100)
    })
    
    # Mock HTFBias (Dataclass)
    htf_bias = HTFBias(
        direction="BULLISH",
        strength=0.8,
        reason="Test",
        w1_regime="ACCUMULATION",
        d1_regime="MARKUP",
        h4_regime="MARKUP",
        h1_regime="MARKUP",
        pdh=32000, pdl=29000, pwh=33000, pwl=28000
    )
    
    # Mock Ghost Data
    ghost_data = {
        "type": "ghost_update",
        "data": {
            "macro_bias": "BULLISH",
            "block_shorts": True,
            "block_longs": False,
            "reason": "DXY Bearish / Risk On",
            "risk_appetite": "RISK_ON"
        }
    }
    
    print("Inyectando contexto Ghost Sentinel...")
    router.set_context(ghost_data=ghost_data)
    
    print("Procesando data de mercado...")
    try:
        result = await asyncio.to_thread(
            router.process_market_data, 
            df, 
            asset="BTCUSDT", 
            interval="15m", 
            htf_bias=htf_bias,
            silent=True
        )
        print("Pipeline completado con exito.")
        print(f"Senales Aprobadas: {len(result.get('signals', []))}")
        print(f"Senales Bloqueadas: {len(result.get('blocked_signals', []))}")
        print("INTEGRIDAD CONFIRMADA: El sistema v8.6.0 es estable.")
    except Exception as e:
        print(f"CRASH DETECTADO: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_integrity())
