
import asyncio
import httpx
import sys
import os

# Anadir el path del proyecto
sys.path.append(os.getcwd())

from engine.indicators.ghost_data import fetch_funding_rate
from engine.core.logger import logger

async def audit_ghost_engine():
    print("AUDITORIA PROFESIONAL DE MOTOR GHOST DATA v8.5.7")
    print("-" * 50)
    
    symbols = ["BTCUSDT", "ETHUSDT", "PAXGUSDT"]
    
    for symbol in symbols:
        print(f"Checking {symbol}...")
        try:
            # Prueba 1: Endpoint Directo
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"https://fapi.binance.com/fapi/v1/fundingRate", params={"symbol": symbol, "limit": 1})
                direct_val = resp.json()[-1]['fundingRate']
                print(f"  [DIRECT] API Raw: {direct_val}")
            
            # Prueba 2: Funcion ghost_data.py
            ghost_val = await fetch_funding_rate(symbol)
            print(f"  [GHOST]  Engine Value: {ghost_val}%")
            
            if ghost_val == 0.0 and float(direct_val) != 0.0:
                print(f"  ERROR DETECTADO: El motor Ghost Data esta bloqueando a {symbol}")
            else:
                print(f"  OK")
                
        except Exception as e:
            print(f"  FALLO CRITICO en {symbol}: {e}")
        print("-" * 30)

if __name__ == "__main__":
    asyncio.run(audit_ghost_engine())
