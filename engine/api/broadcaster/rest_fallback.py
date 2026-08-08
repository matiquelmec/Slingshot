import asyncio
import time
import httpx
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
        self.poll_interval = 2.5  # [v10.2.2] Incrementado para reducir carga REST
        self.last_kline = None    # Cache para inyectar precio live desde el depth
        
        # Mapeo de intervalos Slingshot -> Bitunix
        self.interval_map = {
            "1m": "1m",
            "3m": "3m",
            "5m": "5m",
            "15m": "15m",
            "1h": "1h",
            "4h": "4h",
            "1d": "1d"
        }
        
        # Duración de intervalos en ms
        self.duration_map = {
            "1m": 60000,
            "3m": 180000,
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
        try:
            await self.bc._broadcast({
                "type": "connection_mode",
                "data": {"symbol": self.symbol, "mode": "FALLBACK"}
            })
        except Exception:
            pass
        asyncio.create_task(self._poll_loop())

    async def stop(self):
        if not self.is_running: return
        self.is_running = False
        logger.info(f"🛑 [FALLBACK] Deteniendo Bitunix Telemetry para {self.symbol}")
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
            async with httpx.AsyncClient(timeout=10.0) as client:
                while self.is_running:
                    try:
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
                        else:
                            logger.warning(f"[FALLBACK] Bitunix kline error: {response.status_code}")
                        
                        # Polling de Profundidad (Orderbook) para el Heatmap
                        depth_resp = await client.get(depth_url, params={"symbol": self.symbol})
                        if depth_resp.status_code == 200:
                            depth_data = depth_resp.json()
                            if depth_data.get("code") == 0 and depth_data.get("data"):
                                await self._process_bitunix_depth(depth_data["data"])
                        else:
                            logger.warning(f"[FALLBACK] Bitunix depth error: {depth_resp.status_code}")
                        
                    except httpx.TimeoutException:
                        logger.debug(f"[FALLBACK] Bitunix timeout (10s) en {self.symbol} - Reintentando...")
                    except Exception as e:
                        logger.error(f"[FALLBACK] Error crítico en loop de Bitunix ({self.symbol}): {e}")
                    
                    await asyncio.sleep(self.poll_interval)
        finally:
            logger.info(f"🔌 [FALLBACK] Recursos HTTP liberados para {self.symbol}")

    async def _process_bitunix_kline(self, k: dict):
        """
        Traduce el formato de Bitunix al formato interno de Slingshot (Binance compatible).
        """
        try:
            # Reconstruir el payload que espera el pipeline
            event_time = int(time.time() * 1000)
            
            # Nota: Bitunix 'time' es el inicio de la vela
            kline_ts = int(k["time"])
            
            # Detectar si el timestamp de la vela cambió para emitir el cierre de la vela anterior
            if self.last_kline and self.last_kline.get("k", {}).get("t") != kline_ts:
                logger.info(f"📊 [FALLBACK-CLOSE] Detectado cierre de vela para {self.symbol}:{self.interval} (TS anterior: {self.last_kline['k']['t']} -> Nuevo: {kline_ts})")
                closed_payload = self.last_kline.copy()
                # Marcar la vela anterior como CERRADA para forzar el pipeline de estrategias
                closed_payload["k"] = closed_payload["k"].copy()
                closed_payload["k"]["x"] = True
                await self.bc._process_kline_stream(closed_payload, {"data": closed_payload, "stream": "fallback_close"})
            
            # Simulamos el formato de Binance WebSocket (Abierto)
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
                    "x": False # Se emitirá como True al detectar cambio de timestamp en la siguiente iteración
                }
            }
            
            # Enviar directamente al procesador de klines del broadcaster
            # Esto sincroniza el latestPrice y dispara el Fast Path
            self.last_kline = binance_payload # Guardamos para el inyector de depth e identificar el próximo cierre
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
