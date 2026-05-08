from typing import Dict, Optional, List, Set
from collections import deque
import asyncio

class BroadcasterState:
    """
    Encapsula el estado interno de un SymbolBroadcaster.
    Facilita la modularización al separar los datos de la lógica de red.
    """
    def __init__(self, symbol: str, interval: str):
        self.symbol = symbol.upper()
        self.interval = interval
        
        # Estado de Mercado (Caché para hidratación)
        self.last_ghost: Optional[dict] = None
        self.last_smc: Optional[dict] = None
        self.last_tactical: Optional[dict] = None
        self.last_session: Optional[dict] = None
        self.last_advisor: Optional[dict] = None
        self.last_liquidations: Optional[dict] = None
        self.last_onchain: Optional[dict] = None
        
        # Métricas y Buffers
        self.history: List[dict] = []
        self.live_buffer: deque = deque(maxlen=300)
        self.ml_projection = {"direction": "CALIBRANDO", "probability": 50, "status": "warmup"}
        self.ema_ml_prob = 50.0
        self.htf_bias = None
        self.last_htf_bias_msg: Optional[dict] = None
        self.last_htf_ts = 0.0
        self.live_rvol: float = 0.0
        
        # Control de Tareas
        self.first_advisor_done = False
        self.last_advisor_ts = 0
        self.last_pulse_ts = 0.0
        self.candle_closes = 0
        
        # Heatmap
        self.heatmap = {"hot_bids": [], "hot_asks": [], "imbalance": 0.0}
        self.liquidity = {"bids": [], "asks": []}
        
        # Precio en tiempo real (escritura directa desde kline stream)
        self._latest_price: float = 0.0
        
        # Bloqueo de concurrencia
        self.lock = asyncio.Lock()
        
    def to_dict(self):
        return {
            "symbol": self.symbol,
            "interval": self.interval,
            "latest_price": self.latest_price
        }

    @property
    def latest_price(self) -> float:
        # Primero: precio en tiempo real del stream de klines
        if self._latest_price > 0:
            return self._latest_price
        # Fallback: último close del buffer
        if self.live_buffer:
            return float(self.live_buffer[-1]["data"].get("close", 0.0))
        if self.history:
            return float(self.history[-1]["data"].get("close", 0.0))
        return 0.0

    @latest_price.setter
    def latest_price(self, value: float):
        self._latest_price = value
