import httpx
import asyncio
import random
from engine.core.logger import logger
from engine.api.config import settings

# Activos que solo existen en Binance SPOT (no en futuros perpetuos)
_SPOT_ONLY = settings.SPOT_ONLY_ASSETS

async def fetch_binance_history(symbol: str, interval: str = "15m", limit: int = 300) -> list:
    """Descarga velas históricas desde Binance REST. Retorna lista de dicts estandarizados."""
    sym = symbol.upper()
    # Selección dinámica de endpoint: SPOT vs FUTUROS
    if sym in _SPOT_ONLY:
        url = "https://api.binance.com/api/v3/klines"
        mirror_url = "https://api1.binance.com/api/v3/klines"
    else:
        url = "https://fapi.binance.com/fapi/v1/klines"
        mirror_url = "https://fapi1.binance.com/fapi/v1/klines"

    params = {"symbol": sym, "interval": interval, "limit": limit}
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            await asyncio.sleep(random.uniform(0.1, 0.5) * attempt)
            
            async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
                response = await client.get(url, params=params)
                if response.status_code == 429:
                    wait_time = int(response.headers.get("Retry-After", 2))
                    logger.warning(f"[HISTORY] Rate Limited (429) for {sym}. Esperando {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                
                if response.status_code != 200:
                    response = await client.get(mirror_url, params=params)
                
                response.raise_for_status()
                raw = response.json()
                
                candles = [
                    {"type": "candle", "data": {
                        "timestamp": k[0] / 1000,
                        "open": float(k[1]), "high": float(k[2]),
                        "low": float(k[3]),  "close": float(k[4]),
                        "volume": float(k[5]),
                    }}
                    for k in raw
                ]
                
                # ── INTEGRACIÓN DE CO-PROCESAMIENTO HFT SIDECAR ──
                # Hidratamos el cierre y volumen de la vela en desarrollo con la caché de Node.js
                if candles:
                    try:
                        async with httpx.AsyncClient(timeout=0.08) as local_client: # Límite estricto de 80ms
                            local_res = await local_client.get("http://127.0.0.1:8080/ticks")
                            if local_res.status_code == 200:
                                ticks = local_res.json()
                                asset_tick = ticks.get(sym)
                                if asset_tick and asset_tick.get("price", 0) > 0:
                                    last_candle = candles[-1]["data"]
                                    last_candle["close"] = asset_tick["price"]
                                    # Evitar que una mecha de Binance supere el High/Low del tick HFT
                                    last_candle["high"] = max(last_candle["high"], asset_tick["price"])
                                    last_candle["low"] = min(last_candle["low"], asset_tick["price"])
                                    # Loggear optimización de latencia en depuración
                                    logger.debug(f"[SIDECAR_HFT] Vela en desarrollo de {sym} optimizada con WebSocket Local.")
                    except Exception:
                        # Fallback silencioso: Si el Sidecar de Node.js está apagado, 
                        # el sistema sigue con las velas REST normales sin fallar.
                        pass
                
                return candles
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"[HISTORY] Error final descargando {sym}:{interval} tras {max_retries} intentos: {e}")
                return []
            await asyncio.sleep(1.0 * (attempt + 1))
    return []
