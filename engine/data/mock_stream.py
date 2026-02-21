import json
import asyncio
import time
import random
from typing import Callable, Awaitable
from ..api.ws_manager import manager

class MockStream:
    """
    Generador de datos MOCK (Simulados) para desarrollo local.
    Útil cuando las APIs reales (Binance/CryptoCompare) bloquean la IP por región.
    Simula el formato exacto de Binance para testear el motor de SMC sin dependencias de red.
    """
    
    def __init__(self, symbol: str, interval: str = "1m"):
        self.symbol = symbol.lower()
        self.interval = interval
        self.is_running = False
        self.current_price = 95000.00 # Precio base de simulacion (BTC)

    async def start(self, callback: Callable[[dict], Awaitable[None]] = None):
        """Inicia la generación de ticks simulados ohlcv."""
        self.is_running = True
        print(f"Connected to MOCK LOCAL WS: {self.symbol}@{self.interval}")
        
        while self.is_running:
            try:
                # Simular variabilidad de mercado (Random Walk simple)
                change = random.uniform(-10.0, 10.0)
                self.current_price += change
                
                now_ms = int(time.time() * 1000)
                
                # Crear un payload idéntico al que entregaría BinanceStream
                payload = {
                    "type": "kline",
                    "symbol": self.symbol.upper(),
                    "source": "mock_local",
                    "data": {
                        "t": now_ms - 60000, # Open time simulado
                        "o": self.current_price - random.uniform(0, 5), # Open
                        "h": self.current_price + random.uniform(0, 15), # High
                        "l": self.current_price - random.uniform(0, 15), # Low
                        "c": self.current_price, # Close actual
                        "v": random.uniform(0.1, 5.0), # Volumen aleatorio
                        "closed": random.random() > 0.8 # 20% de probabilidad de cerrar vela
                    }
                }
                
                # Broadcast local (simula ws_manager)
                await manager.broadcast(payload)
                
                if callback:
                    await callback(payload)
                    
                # Emitir un tick cada 1.5 segundos para no inundar el log pero mantener el flujo
                await asyncio.sleep(1.5)
                
            except getattr(asyncio.exceptions, 'CancelledError', asyncio.CancelledError):
                break
            except Exception as e:
                print(f"Mock WS Error: {e}")
                await asyncio.sleep(2)

    def stop(self):
        self.is_running = False
