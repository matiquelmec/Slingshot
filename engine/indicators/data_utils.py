import httpx
import asyncio
import random
from engine.core.logger import logger

async def fetch_binance_history(symbol: str, interval: str = "15m", limit: int = 300) -> list:
    """Descarga velas históricas desde Binance REST. Retorna lista de dicts estandarizados."""
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {"symbol": symbol.upper(), "interval": interval, "limit": limit}
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            await asyncio.sleep(random.uniform(0.1, 0.5) * attempt)
            
            async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
                response = await client.get(url, params=params)
                if response.status_code == 429:
                    wait_time = int(response.headers.get("Retry-After", 2))
                    logger.warning(f"[HISTORY] Rate Limited (429) for {symbol}. Esperando {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                
                if response.status_code != 200:
                    mirror_url = "https://fapi1.binance.com/fapi/v1/klines"
                    response = await client.get(mirror_url, params=params)
                
                response.raise_for_status()
                raw = response.json()
                return [
                    {"type": "candle", "data": {
                        "timestamp": k[0] / 1000,
                        "open": float(k[1]), "high": float(k[2]),
                        "low": float(k[3]),  "close": float(k[4]),
                        "volume": float(k[5]),
                    }}
                    for k in raw
                ]
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"[HISTORY] Error final descargando {symbol}:{interval} tras {max_retries} intentos: {e}")
                return []
            await asyncio.sleep(1.0 * (attempt + 1))
    return []
