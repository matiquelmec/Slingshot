import asyncio
import websockets
import json
import pandas as pd
from typing import Callable, Dict, Any, Optional

class BinanceStreamer:
    """
    Gestor de WebSockets para Binance (Capa 1).
    Mantiene conexiones persistentes, maneja desconexiones, 
    y formatea los mensajes en crudo a objetos compatibles con Pandas.
    """
    
    def __init__(self, callbacks: list[Callable] = None):
        self.base_url = "wss://stream.binance.com:9443/ws"
        # URL combinada para múltiples streams: wss://stream.binance.com:9443/stream?streams=<streamName1>/<streamName2>
        self.combined_url = "wss://stream.binance.com:9443/stream?streams="
        self.callbacks = callbacks or []
        self.active = False
        self.ws: Optional[websockets.WebSocketClientProtocol] = None

    async def connect_single(self, symbol: str, interval: str = "15m"):
        """
        Conecta a un único stream de Klines (Velas).
        """
        self.active = True
        stream_name = f"{symbol.lower()}@kline_{interval}"
        url = f"{self.base_url}/{stream_name}"
        
        print(f"📡 Intentando conectar a Binance WS: {stream_name}")
        
        while self.active:
            try:
                async with websockets.connect(url) as ws:
                    self.ws = ws
                    print(f"✅ Conectado a Binance WS ({symbol} {interval})")
                    
                    while self.active:
                        message = await ws.recv()
                        await self._process_message(message)
                        
            except websockets.exceptions.ConnectionClosedError as e:
                print(f"⚠️ Conexión cerrada inesperadamente. Reintentando en 5s... ({e})")
                await asyncio.sleep(5)
            except Exception as e:
                print(f"❌ Error en Binance WS: {e}. Reintentando en 5s...")
                await asyncio.sleep(5)
                
    async def connect_multiplex(self, symbols: list[str], interval: str = "15m"):
        """
        Conecta a múltiples streams simultáneamente (Avanzado).
        """
        self.active = True
        streams = [f"{sym.lower()}@kline_{interval}" for sym in symbols]
        url = self.combined_url + "/".join(streams)
        
        print(f"📡 Intentando conectar a Binance MULTIPLEX WS: {len(symbols)} activos")
        
        while self.active:
            try:
                async with websockets.connect(url) as ws:
                    self.ws = ws
                    print(f"✅ Conectado a Binance MULTIPLEX WS")
                    
                    while self.active:
                        message = await ws.recv()
                        # Formato diferente para streams combinados
                        data = json.loads(message)
                        await self._process_message(json.dumps(data['data']))
                        
            except Exception as e:
                print(f"❌ Error en Binance MULTIPLEX WS: {e}. Reintentando en 5s...")
                await asyncio.sleep(5)

    async def _process_message(self, message: str):
        """
        Parsea el JSON crudo de Binance y lo convierte en un diccionario estandarizado.
        """
        try:
            data = json.loads(message)
            
            # Formato de Kline (Vela) de Binance
            kline = data.get('k')
            if not kline:
                return

            parsed_data = {
                "symbol": kline['s'],
                "interval": kline['i'],
                "timestamp": pd.to_datetime(kline['t'], unit='ms', utc=True),
                "open": float(kline['o']),
                "high": float(kline['h']),
                "low": float(kline['l']),
                "close": float(kline['c']),
                "volume": float(kline['v']),
                "is_closed": kline['x'], # True si la vela se cerró
                "number_of_trades": int(kline['n']),
                "taker_buy_base": float(kline['V']) # Buy Volume (CVD)
            }
            
            # Enviar la data procesada a todos los callbacks registrados
            for callback in self.callbacks:
                if asyncio.iscoroutinefunction(callback):
                    await callback(parsed_data)
                else:
                    callback(parsed_data)
                    
        except Exception as e:
            print(f"Error parseando mensaje WS: {e}")

    def stop(self):
        """Detiene el bucle de reconexión."""
        self.active = False
        print("🛑 Deteniendo Binance WS...")

if __name__ == "__main__":
    # Prueba rápida del Streamer
    async def sample_callback(data: dict):
        if data['is_closed']:
            print(f"🔔 VELA CERRADA: {data['symbol']} | Cierre: ${data['close']} | Vol: {data['volume']}")
        else:
            # Imprimir tick actual (Opcional, puede ser mucho spam)
            print(f"Tick: {data['symbol']} -> ${data['close']}", end='\r')

    async def run_test():
        streamer = BinanceStreamer(callbacks=[sample_callback])
        # Correr 10 segundos y apagar
        task = asyncio.create_task(streamer.connect_single("BTCUSDT", "1m"))
        await asyncio.sleep(10)
        streamer.stop()
        task.cancel()
        
    asyncio.run(run_test())
