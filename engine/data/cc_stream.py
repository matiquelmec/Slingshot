import json
import asyncio
import websockets
import ssl
import certifi
from typing import Callable, Awaitable
from ..api.ws_manager import manager

class CryptoCompareStream:
    """Manejador de WebSockets de CryptoCompare como Fallback robusto."""
    
    def __init__(self, symbol: str, api_key: str = ""):
        # CryptoCompare espera pares unidos, ej: BTCUSD
        self.symbol = symbol.upper().replace('USDT', 'USD')
        self.api_key = api_key
        # API_KEY es requerida para CryptoCompare. Si no hay, usa una conexion publica limitada o falla.
        self.url = f"wss://streamer.cryptocompare.com/v2?api_key={self.api_key}"
        self.is_running = False

    async def start(self, callback: Callable[[dict], Awaitable[None]] = None):
        """Inicia la conexión y procesa los eventos."""
        self.is_running = True
        
        # Contexto SSL para evitar errores de certificado
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        
        while self.is_running:
            try:
                async with websockets.connect(self.url, ssl=ssl_context) as ws:
                    print(f"Connected to CryptoCompare WS: {self.symbol}")
                    
                    # Suscribirse al canal "24" (Trade) o "5" (Aggregate Index)
                    # Usamos 5 (Current minute OHLCV) para simular klines
                    sub_message = {
                        "action": "SubAdd",
                        "subs": [f"24~CCCAGG~{self.symbol[:3]}~{self.symbol[3:]}"]
                    }
                    await ws.send(json.dumps(sub_message))
                    
                    while self.is_running:
                        message = await ws.recv()
                        data = json.loads(message)
                        
                        # Tipo 24 es OHLCV agregado por minuto
                        if str(data.get('TYPE')) == '24':
                            payload = {
                                "type": "kline",
                                "symbol": self.symbol,
                                "source": "cryptocompare",
                                "data": {
                                    "t": data.get('TS', 0) * 1000,
                                    "o": data.get('OPEN24HOUR', 0),
                                    "h": data.get('HIGH24HOUR', 0),
                                    "l": data.get('LOW24HOUR', 0),
                                    "c": data.get('PRICE', 0),
                                    "v": data.get('VOLUME24HOUR', 0),
                                    "closed": True # CryptoCompare 24 type sends updates, we assume closed for now
                                }
                            }
                            
                            # Broadcast a clientes locales (UI)
                            await manager.broadcast(payload)
                            
                            if callback:
                                await callback(payload)
                                
            except Exception as e:
                print(f"CryptoCompare WS Connection lost: {e}. Retrying in 5s...")
                await asyncio.sleep(5)

    def stop(self):
        self.is_running = False
