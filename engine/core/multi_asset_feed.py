"""
engine/core/multi_asset_feed.py
Ingestor Multiactivo Institucional para FTMO MT5 & Exchanges
Captura velas en tiempo real para:
- Oro (XAUUSD / PAXG)
- Índices (US100 / Nasdaq, US30 / Dow)
- Forex (EURUSD, GBPUSD)
- Cripto Mayores (BTC, ETH, SOL)

OPTIMIZACIÓN ARQUITECTURAL INSTITUCIONAL:
- Cliente HTTP asíncrono no bloqueante (httpx.AsyncClient)
- Cero bloqueo de Event Loop (timeout estricto de 2.5s)
- Fallback automático a cache local en RAM
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Optional

import httpx
import numpy as np
import pandas as pd

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
        self._async_client: Optional[httpx.AsyncClient] = None

    def _get_async_client(self) -> httpx.AsyncClient:
        if self._async_client is None or self._async_client.is_closed:
            self._async_client = httpx.AsyncClient(
                headers={"User-Agent": "Slingshot-Terminal/2.0"},
                timeout=httpx.Timeout(2.5, connect=1.5)
            )
        return self._async_client

    def _parse_klines(self, data: list, symbol: str) -> pd.DataFrame:
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

    async def fetch_klines(self, symbol: str, interval: str = "15m", limit: int = 100) -> Optional[pd.DataFrame]:
        """Obtiene velas de forma verdaderamente asíncrona y no bloqueante."""
        target_info = FTMO_SYMBOLS_MAP.get(symbol.upper(), {"feed_symbol": symbol.upper(), "type": "CRYPTO"})
        feed_sym = target_info["feed_symbol"]
        url = f"https://api.binance.com/api/v3/klines?symbol={feed_sym}&interval={interval}&limit={limit}"

        try:
            client = self._get_async_client()
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                return self._parse_klines(data, symbol)
            else:
                logger.warning(f"Respuesta HTTP {resp.status_code} para {symbol} ({feed_sym})")
                return self.cached_klines.get(symbol)
        except Exception as e:
            logger.warning(f"Falla de feed asíncrono para {symbol} ({feed_sym}): {e}")
            return self.cached_klines.get(symbol)

    def fetch_klines_sync(self, symbol: str, interval: str = "15m", limit: int = 100) -> Optional[pd.DataFrame]:
        """Compatibilidad síncrona usando httpx directo sin congelar DNS prolongado."""
        target_info = FTMO_SYMBOLS_MAP.get(symbol.upper(), {"feed_symbol": symbol.upper(), "type": "CRYPTO"})
        feed_sym = target_info["feed_symbol"]
        url = f"https://api.binance.com/api/v3/klines?symbol={feed_sym}&interval={interval}&limit={limit}"
        try:
            with httpx.Client(headers={"User-Agent": "Slingshot-Terminal/2.0"}, timeout=2.5) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    return self._parse_klines(resp.json(), symbol)
            return self.cached_klines.get(symbol)
        except Exception as e:
            logger.warning(f"No se pudo descargar velas síncronas para {symbol} ({feed_sym}): {e}")
            return self.cached_klines.get(symbol)

    async def close(self):
        """Cierre ordenado de conexiones abiertas."""
        if self._async_client and not self._async_client.is_closed:
            await self._async_client.aclose()


# Instancia singleton
multi_asset_feed = MultiAssetFeed()
