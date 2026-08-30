"""
engine/api/broadcaster/rest_fallback.py — v26.1 (STREAM FORTRESS)
=============================================================================
Sistema de Telemetría de Rescate vía Bitunix REST.
Incluye:
  1. Token Bucket Rate Limiter compartido (máx 3 req/s) para evitar sobrecargar Bitunix.
  2. Pool de conexiones HTTP persistente compartido.
  3. Manejo silencioso y elegante de timeouts transitorios.
"""
import asyncio
import time
from typing import Optional
import httpx
from engine.core.logger import logger
from engine.api.config import settings

class AsyncTokenBucket:
    """
    Token Bucket Rate Limiter asíncrono singleton.
    Garantiza una tasa global máxima de peticiones por segundo compartida entre todos los activos.
    """
    def __init__(self, rate_per_sec: float = 3.0, burst: int = 5):
        self.rate = rate_per_sec
        self.burst = burst
        self.tokens = float(burst)
        self.last_update = time.time()
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            now = time.time()
            elapsed = max(0.0, now - self.last_update)
            self.tokens = min(float(self.burst), self.tokens + elapsed * self.rate)
            self.last_update = now
            if self.tokens < 1.0:
                wait_time = (1.0 - self.tokens) / self.rate
                await asyncio.sleep(wait_time)
                self.tokens = 0.0
                self.last_update = time.time()
            else:
                self.tokens -= 1.0

# Singleton global compartido para Bitunix REST
_bitunix_rate_limiter = AsyncTokenBucket(rate_per_sec=3.0, burst=5)
_shared_client: Optional[httpx.AsyncClient] = None
_client_lock = asyncio.Lock()

async def get_shared_client() -> httpx.AsyncClient:
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        async with _client_lock:
            if _shared_client is None or _shared_client.is_closed:
                _shared_client = httpx.AsyncClient(
                    timeout=httpx.Timeout(8.0, connect=4.0),
                    limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
                )
    return _shared_client


class BitunixFallback:
    """
    Sistema de Telemetría de Rescate vía Bitunix REST.
    Se activa de forma controlada cuando los WebSockets de Binance están reconectando.
    """
    def __init__(self, symbol: str, interval: str, broadcaster):
        self.symbol = symbol.upper()
        self.interval = interval
        self.bc = broadcaster
        self.is_running = False
        self.poll_interval = 2.5
        self.last_kline = None
        
        self.interval_map = {
            "1m": "1m", "3m": "3m", "5m": "5m",
            "15m": "15m", "1h": "1h", "4h": "4h", "1d": "1d"
        }
        
        self.duration_map = {
            "1m": 60000, "3m": 180000, "5m": 300000,
            "15m": 900000, "1h": 3600000, "4h": 14400000, "1d": 86400000
        }

    async def start(self):
        if self.is_running:
            return
        self.is_running = True
        logger.info(f"🛡️ [FALLBACK] Activando Bitunix Telemetry controlada para {self.symbol}...")
        try:
            await self.bc._broadcast({
                "type": "connection_mode",
                "data": {"symbol": self.symbol, "mode": "FALLBACK"}
            })
        except Exception:
            pass
        asyncio.create_task(self._poll_loop())

    async def stop(self):
        if not self.is_running:
            return
        self.is_running = False
        logger.info(f"🛑 [FALLBACK] Deteniendo Bitunix Telemetry para {self.symbol} (WS Activo)")
        try:
            await self.bc._broadcast({
                "type": "connection_mode",
                "data": {"symbol": self.symbol, "mode": "WS"}
            })
        except Exception:
            pass

    async def _poll_loop(self):
        url = "https://fapi.bitunix.com/api/v1/futures/market/kline"
        depth_url = "https://fapi.bitunix.com/api/v1/futures/market/depth"
        bitunix_interval = self.interval_map.get(self.interval, "1m")
        
        try:
            while self.is_running:
                try:
                    client = await get_shared_client()
                    
                    # 1. Rate limiter token acquisition
                    await _bitunix_rate_limiter.acquire()
                    if not self.is_running:
                        break
                        
                    params = {
                        "symbol": self.symbol,
                        "interval": bitunix_interval,
                        "limit": 1
                    }
                    
                    response = await client.get(url, params=params)
                    
                    if response.status_code == 200:
                        data = response.json()
                        if data.get("code") == 0 and data.get("data"):
                            k = data["data"][0]
                            await self._process_bitunix_kline(k)
                    elif response.status_code != 429:
                        logger.debug(f"[FALLBACK] Bitunix kline code {response.status_code} para {self.symbol}")
                    
                    # 2. Polling de Profundidad controlado por rate-limit
                    await _bitunix_rate_limiter.acquire()
                    if not self.is_running:
                        break
                        
                    depth_resp = await client.get(depth_url, params={"symbol": self.symbol})
                    if depth_resp.status_code == 200:
                        depth_data = depth_resp.json()
                        if depth_data.get("code") == 0 and depth_data.get("data"):
                            await self._process_bitunix_depth(depth_data["data"])
                            
                except httpx.TimeoutException:
                    logger.debug(f"[FALLBACK] Bitunix polling timeout transitorio en {self.symbol} (reintentando en {self.poll_interval}s)")
                except Exception as e:
                    logger.debug(f"[FALLBACK] Error transitorio en loop de Bitunix ({self.symbol}): {e}")
                
                await asyncio.sleep(self.poll_interval)
        finally:
            logger.debug(f"🔌 [FALLBACK] Ciclo finalizado para {self.symbol}")

    async def _process_bitunix_kline(self, k: dict):
        """Traduce el formato de Bitunix al formato interno de Slingshot (Binance compatible)."""
        try:
            event_time = int(time.time() * 1000)
            kline_ts = int(k["time"])
            
            if self.last_kline and self.last_kline.get("k", {}).get("t") != kline_ts:
                closed_payload = self.last_kline.copy()
                closed_payload["k"] = closed_payload["k"].copy()
                closed_payload["k"]["x"] = True
                await self.bc._process_kline_stream(closed_payload, {"data": closed_payload, "stream": "fallback_close"})
            
            binance_payload = {
                "e": "kline",
                "E": event_time,
                "s": self.symbol,
                "k": {
                    "t": kline_ts,
                    "T": kline_ts + self.duration_map.get(self.interval, 60000) - 1,
                    "s": self.symbol,
                    "i": self.interval,
                    "o": k["open"],
                    "c": k["close"],
                    "h": k["high"],
                    "l": k["low"],
                    "v": k.get("quoteVol", k.get("vol", "0")),
                    "q": k.get("baseVol", k.get("amount", "0")),
                    "x": False
                }
            }
            
            self.last_kline = binance_payload
            await self.bc._process_kline_stream(binance_payload, {"data": binance_payload, "stream": "fallback"})
            
        except Exception as e:
            logger.debug(f"[FALLBACK] Error procesando kline de Bitunix: {e}")

    async def _process_bitunix_depth(self, depth: dict):
        """Traduce el libro de órdenes de Bitunix al formato esperado por Slingshot."""
        try:
            bids = depth.get("bids", [])
            asks = depth.get("asks", [])
            
            if bids and asks:
                best_bid = float(bids[0][0])
                best_ask = float(asks[0][0])
                mid_price = (best_bid + best_ask) / 2
                
                if self.last_kline:
                    live_kline = self.last_kline.copy()
                    if "k" in live_kline:
                        live_kline["k"]["c"] = str(mid_price)
                    elif "data" in live_kline:
                        live_kline["data"]["close"] = str(mid_price)
                    
                    await self.bc._process_kline_stream(live_kline, {"data": live_kline, "stream": "depth_price"})

            payload = {
                "b": bids,
                "a": asks
            }
            await self.bc._process_depth_stream(payload)
            
        except Exception as e:
            logger.debug(f"[FALLBACK] Error procesando profundidad de Bitunix: {e}")