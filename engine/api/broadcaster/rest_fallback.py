import asyncio
import time
import requests
from engine.core.logger import logger
from engine.api.config import settings

class BitunixFallback:
    """
    Sistema de Telemetría de Rescate vía Bitunix REST.
    Se activa cuando los WebSockets de Binance están bloqueados.
    """
    def __init__(self, symbol: str, interval: str, broadcaster):
        self.symbol = symbol.upper()
        self.interval = interval
        self.bc = broadcaster
        self.is_running = False
        self.poll_interval = 1.5  # Segundos entre peticiones
        self.last_kline = None    # Cache para inyectar precio live desde el depth
        
        # Mapeo de intervalos Slingshot -> Bitunix
        self.interval_map = {
            "1m": "1m",
            "5m": "5m",
            "15m": "15m",
            "1h": "1h",
            "4h": "4h",
            "1d": "1d"
        }
        
        # Duración de intervalos en ms
        self.duration_map = {
            "1m": 60000,
            "5m": 300000,
            "15m": 900000,
            "1h": 3600000,
            "4h": 14400000,
            "1d": 86400000
        }

    async def start(self):
        if self.is_running: return
        self.is_running = True
        logger.info(f"🚨 [FALLBACK] Activando Bitunix Telemetry para {self.symbol}...")
        asyncio.create_task(self._poll_loop())

    async def stop(self):
        self.is_running = False
        logger.info(f"🛑 [FALLBACK] Deteniendo Bitunix Telemetry para {self.symbol}")

    async def _poll_loop(self):
        url = "https://fapi.bitunix.com/api/v1/futures/market/kline"
        bitunix_interval = self.interval_map.get(self.interval, "1m")
        
        while self.is_running:
            try:
                # Usar asyncio.to_thread para no bloquear el loop con requests
                params = {
                    "symbol": self.symbol,
                    "interval": bitunix_interval,
                    "limit": 1
                }
                
                response = await asyncio.to_thread(
                    requests.get, url, params=params, timeout=5
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("code") == 0 and data.get("data"):
                        k = data["data"][0]
                        await self._process_bitunix_kline(k)
                
                # Polling de Profundidad (Orderbook) para el Heatmap
                depth_url = "https://fapi.bitunix.com/api/v1/futures/market/depth"
                depth_resp = await asyncio.to_thread(
                    requests.get, depth_url, params={"symbol": self.symbol}, timeout=5
                )
                if depth_resp.status_code == 200:
                    depth_data = depth_resp.json()
                    if depth_data.get("code") == 0 and depth_data.get("data"):
                        await self._process_bitunix_depth(depth_data["data"])
                
                else:
                    logger.warning(f"[FALLBACK] Bitunix error: {response.status_code}")
                
            except Exception as e:
                logger.error(f"[FALLBACK] Error en loop de Bitunix: {e}")
            
            await asyncio.sleep(self.poll_interval)

    async def _process_bitunix_kline(self, k: dict):
        """
        Traduce el formato de Bitunix al formato interno de Slingshot (Binance compatible).
        """
        try:
            # Reconstruir el payload que espera el pipeline
            event_time = int(time.time() * 1000)
            
            # Nota: Bitunix 'time' es el inicio de la vela
            kline_ts = int(k["time"])
            
            # Simulamos el formato de Binance WebSocket
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
                    "v": k["quoteVol"],
                    "q": k["baseVol"],
                    "x": False # El fallback no detecta cierre de vela tan fácil, lo dejamos en False
                }
            }
            
            # Enviar directamente al procesador de klines del broadcaster
            # Esto sincroniza el latestPrice y dispara el Fast Path
            self.last_kline = binance_payload # Guardamos para el inyector de depth
            await self.bc._process_kline_stream(binance_payload, {"data": binance_payload, "stream": "fallback"})
            
        except Exception as e:
            logger.error(f"[FALLBACK] Error procesando kline de Bitunix: {e}")

    async def _process_bitunix_depth(self, depth: dict):
        """
        Traduce el libro de órdenes de Bitunix al formato esperado por Slingshot
        y extrae el precio actual para mover el gráfico.
        """
        try:
            bids = depth.get("bids", [])
            asks = depth.get("asks", [])
            
            # 1. Extraer precio "Live" del spread
            if bids and asks:
                best_bid = float(bids[0][0])
                best_ask = float(asks[0][0])
                mid_price = (best_bid + best_ask) / 2
                
                # Si tenemos un kline base, actualizamos su 'close' con el precio real-time
                if self.last_kline:
                    live_kline = self.last_kline.copy()
                    # Si es formato Binance WS
                    if "k" in live_kline:
                        live_kline["k"]["c"] = str(mid_price)
                    # Si es formato REST/Directo
                    elif "data" in live_kline:
                        live_kline["data"]["close"] = str(mid_price)
                    
                    # Forzar actualización de alta prioridad
                    await self.bc._process_kline_stream(live_kline, {"data": live_kline, "stream": "depth_price"})

            # 2. Procesar para el Heatmap
            payload = {
                "b": bids,
                "a": asks
            }
            await self.bc._process_depth_stream(payload)
            
        except Exception as e:
            logger.error(f"[FALLBACK] Error procesando profundidad de Bitunix: {e}")
