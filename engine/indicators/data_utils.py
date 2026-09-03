import httpx
import asyncio
import random
from engine.core.logger import logger
from engine.api.config import settings

# Activos que solo existen en Binance SPOT (no en futuros perpetuos)
_SPOT_ONLY = settings.SPOT_ONLY_ASSETS

# Connection Pool persistente para reusar handshakes TCP/TLS y evitar latencia de 1-2s por llamada
_HTTP_CLIENT = httpx.AsyncClient(timeout=8.0, follow_redirects=True, limits=httpx.Limits(max_keepalive_connections=50, max_connections=100))

async def fetch_binance_history(symbol: str, interval: str = "15m", limit: int = 300) -> list:
    """Descarga velas históricas desde Binance REST con pool de conexión persistente (sub-200ms)."""
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
            if attempt > 0:
                await asyncio.sleep(0.3 * attempt)
            
            response = await _HTTP_CLIENT.get(url, params=params)
            if response.status_code == 429:
                wait_time = int(response.headers.get("Retry-After", 2))
                logger.warning(f"[HISTORY] Rate Limited (429) for {sym}. Esperando {wait_time}s...")
                await asyncio.sleep(wait_time)
                continue
            
            if response.status_code != 200:
                response = await _HTTP_CLIENT.get(mirror_url, params=params)
            
            response.raise_for_status()
            raw = response.json()
            
            candles = []
            for k in raw:
                vol = float(k[5])
                taker_buy = float(k[9]) if len(k) > 9 else vol * 0.5
                taker_buy_quote = float(k[10]) if len(k) > 10 else 0.0
                trades_count = int(k[8]) if len(k) > 8 else 0
                
                # Cálculo matemático exacto de Delta (Taker Buy vs Taker Sell)
                taker_sell = max(0.0, vol - taker_buy)
                delta = ((taker_buy - taker_sell) / (vol + 1e-9)) if vol > 0 else 0.0
                delta_clamped = max(-1.0, min(1.0, delta))
                
                candles.append({
                    "type": "candle",
                    "data": {
                        "timestamp": k[0] / 1000,
                        "open": float(k[1]),
                        "high": float(k[2]),
                        "low": float(k[3]),
                        "close": float(k[4]),
                        "volume": vol,
                        "taker_buy_volume": taker_buy,
                        "taker_sell_volume": taker_sell,
                        "taker_buy_quote": taker_buy_quote,
                        "trades_count": trades_count,
                        "order_flow_delta": delta_clamped,
                        "delta_ratio": delta_clamped
                    }
                })
            
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
                                last_candle["high"] = max(last_candle["high"], asset_tick["price"])
                                last_candle["low"] = min(last_candle["low"], asset_tick["price"])
                except Exception:
                    pass
                
                return candles
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"[HISTORY] Error final descargando {sym}:{interval} tras {max_retries} intentos: {e}")
                return []
            await asyncio.sleep(1.0 * (attempt + 1))
    return []

# Cache en memoria para candidatos líquidos (TTL: 1 hora)
_LIQUID_TICKERS_CACHE = {"timestamp": 0, "tickers": []}

async def fetch_top_liquid_tickers(min_volume_usdt: float = 30_000_000.0, limit: int = 30) -> list[str]:
    """
    [DYNAMIC SCREENER v21.0]
    Descarga el ranking de contratos de futuros USDT con mayor volumen 24h desde Binance.
    Aplica caché en memoria de 1 hora para eliminar latencia y llamadas redundantes.
    """
    import time
    now = time.time()
    if now - _LIQUID_TICKERS_CACHE["timestamp"] < 3600 and _LIQUID_TICKERS_CACHE["tickers"]:
        return _LIQUID_TICKERS_CACHE["tickers"]
        
    url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
    mirror_url = "https://fapi1.binance.com/fapi/v1/ticker/24hr"
    
    try:
        response = await _HTTP_CLIENT.get(url)
        if response.status_code != 200:
            response = await _HTTP_CLIENT.get(mirror_url)
            
        if response.status_code == 200:
            data = response.json()
            # Filtrar pares USDT con volumen quote (USDT) superior al umbral y aplicar SOP-28
            candidates = []
            min_price_usd = 0.10  # [SOP-28 QUALITY GATE] Prohibido micro-tokens con errores de decimales
            for item in data:
                sym = item.get("symbol", "")
                if not sym.endswith("USDT") or "_" in sym:
                    continue
                quote_vol = float(item.get("quoteVolume", 0.0))
                last_price = float(item.get("lastPrice", 0.0))
                
                # SOP-28: Exigir volumen mínimo y precio >= $0.10 USDT
                if quote_vol >= min_volume_usdt and last_price >= min_price_usd:
                    candidates.append((sym, quote_vol))
                    
            # Ordenar de mayor a menor volumen
            candidates.sort(key=lambda x: x[1], reverse=True)
            result = [c[0] for c in candidates[:limit]]
            
            _LIQUID_TICKERS_CACHE["timestamp"] = now
            _LIQUID_TICKERS_CACHE["tickers"] = result
            logger.info(f"🔍 [DYNAMIC SCREENER SOP-28] Descubiertos {len(result)} activos institucionales calificados (Volumen > ${min_volume_usdt/1e6:.0f}M, Precio >= ${min_price_usd}).")
            return result
    except Exception as e:
        logger.debug(f"[DYNAMIC SCREENER] Error consultando ranking 24h: {e}")
        
    return _LIQUID_TICKERS_CACHE["tickers"]
