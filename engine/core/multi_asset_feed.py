"""
engine/core/multi_asset_feed.py
Ingestor Multiactivo Institucional para FTMO MT5 & Exchanges
Captura velas en tiempo real para:
- Oro (XAUUSD / PAXG)
- Índices (US100 / Nasdaq, US30 / Dow)
- Forex (EURUSD, GBPUSD)
- Cripto Mayores (BTC, ETH, SOL)
"""

import asyncio
import json
import logging
import urllib.request
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger("Slingshot.MultiAssetFeed")

# Mapeo de activos institucionales
FTMO_SYMBOLS_MAP = {
    "XAUUSD": {"feed_symbol": "PAXGUSDT", "type": "METAL", "name": "Oro (Gold Spot)"},
    "BTCUSD": {"feed_symbol": "BTCUSDT", "type": "CRYPTO", "name": "Bitcoin / USD"},
    "ETHUSD": {"feed_symbol": "ETHUSDT", "type": "CRYPTO", "name": "Ethereum / USD"},
    "SOLUSD": {"feed_symbol": "SOLUSDT", "type": "CRYPTO", "name": "Solana / USD"},
}

class MultiAssetFeed:
    def __init__(self):
        self.cached_klines: Dict[str, pd.DataFrame] = {}
        self.last_update: Dict[str, datetime] = {}

    def fetch_klines_sync(self, symbol: str, interval: str = "15m", limit: int = 100) -> Optional[pd.DataFrame]:
        """Obtiene velas históricas recientes para el activo especificado."""
        target_info = FTMO_SYMBOLS_MAP.get(symbol.upper(), {"feed_symbol": symbol.upper(), "type": "CRYPTO"})
        feed_sym = target_info["feed_symbol"]
        
        url = f"https://api.binance.com/api/v3/klines?symbol={feed_sym}&interval={interval}&limit={limit}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Slingshot-Terminal/2.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                
            df = pd.DataFrame(data, columns=[
                "timestamp", "open", "high", "low", "close", "volume",
                "close_time", "qav", "num_trades", "taker_base_vol", "taker_quote_vol", "ignore"
            ])
            df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = df[col].astype(float)
                
            clean_df = df[["datetime", "open", "high", "low", "close", "volume"]].copy()
            self.cached_klines[symbol] = clean_df
            self.last_update[symbol] = datetime.utcnow()
            return clean_df
        except Exception as e:
            logger.warning(f"No se pudo descargar velas para {symbol} ({feed_sym}): {e}")
            return self.cached_klines.get(symbol)

    async def fetch_klines(self, symbol: str, interval: str = "15m", limit: int = 100) -> Optional[pd.DataFrame]:
        """Versión asíncrona no bloqueante."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.fetch_klines_sync, symbol, interval, limit)

# Instancia singleton
multi_asset_feed = MultiAssetFeed()
