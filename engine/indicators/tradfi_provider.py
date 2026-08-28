"""
engine/indicators/tradfi_provider.py — Proveedor de Datos TradFi Multi-Mercado v19.0
==================================================================================
Descarga y gestiona velas e indicadores en tiempo real para activos de MetaTrader 5 / FTMO:
- XAUUSD (Gold Spot)
- US100 (Nasdaq 100 Cash)
- US30 (Dow Jones 30 Cash)
- GBPUSD (Forex)
"""
import time
import httpx
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any
from engine.core.logger import logger
from engine.indicators.polars_engine import polars_engine

TRADFI_ASSETS_CONFIG = {
    "XAUUSD": {
        "ticker": "GC=F",
        "name": "Gold Spot",
        "category": "COMMODITIES",
        "contract_size": 100,
        "spread_usd": 0.18,
        "min_lot": 0.01,
        "pip_value": 1.0,
        "point_size": 0.01
    },
    "US100": {
        "ticker": "NQ=F",
        "name": "Nasdaq 100 Cash",
        "category": "INDICES",
        "contract_size": 1,
        "spread_usd": 1.10,
        "min_lot": 0.1,
        "pip_value": 1.0,
        "point_size": 0.25
    },
    "US30": {
        "ticker": "YM=F",
        "name": "Dow Jones 30 Cash",
        "category": "INDICES",
        "contract_size": 1,
        "spread_usd": 2.20,
        "min_lot": 0.1,
        "pip_value": 1.0,
        "point_size": 1.0
    },
    "US500": {
        "ticker": "ES=F",
        "name": "S&P 500 Cash",
        "category": "INDICES",
        "contract_size": 1,
        "spread_usd": 0.40,
        "min_lot": 0.1,
        "pip_value": 1.0,
        "point_size": 0.25
    },
    "HGUSD": {
        "ticker": "HG=F",
        "name": "Copper High Grade",
        "category": "COMMODITIES",
        "contract_size": 25000,
        "spread_usd": 0.0010,
        "min_lot": 0.01,
        "pip_value": 12.5,
        "point_size": 0.0005
    },
    "GER40": {
        "ticker": "^GDAXI",
        "name": "DAX 40 Germany",
        "category": "INDICES",
        "contract_size": 25,
        "spread_usd": 1.50,
        "min_lot": 0.1,
        "pip_value": 1.0,
        "point_size": 1.0
    },
    "GBPJPY": {
        "ticker": "GBPJPY=X",
        "name": "GBP/JPY Dragon",
        "category": "FOREX",
        "contract_size": 100000,
        "spread_usd": 0.025,
        "min_lot": 0.01,
        "pip_value": 6.8,
        "point_size": 0.01
    },
    "GBPUSD": {
        "ticker": "GBPUSD=X",
        "name": "GBP/USD Forex",
        "category": "FOREX",
        "contract_size": 100000,
        "spread_usd": 0.00005,
        "min_lot": 0.01,
        "pip_value": 10.0,
        "point_size": 0.0001
    }
}

class TradFiProvider:
    """Proveedor y Caché en RAM de Datos TradFi para FTMO."""
    
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._last_fetch_ts: Dict[str, float] = {}
        self._ttl_seconds = 30.0 # Refresco cada 30s
        
    async def get_candles(self, symbol: str, interval: str = "15m", limit: int = 100) -> Optional[pd.DataFrame]:
        """Obtiene velas en tiempo real calculando indicadores con Polars Rust."""
        symbol = symbol.upper()
        if symbol not in TRADFI_ASSETS_CONFIG:
            logger.warning(f"[TRADFI_PROVIDER] Símbolo no soportado: {symbol}")
            return None
            
        spec = TRADFI_ASSETS_CONFIG[symbol]
        ticker = spec["ticker"]
        cache_key = f"{symbol}:{interval}"
        
        now = time.time()
        if cache_key in self._cache and (now - self._last_fetch_ts.get(cache_key, 0)) < self._ttl_seconds:
            return self._cache[cache_key]["df"]
            
        # Mapear intervalo a Yahoo Finance
        yf_interval = "15m" if interval in ("15m", "5m") else "1h" if interval in ("1h", "4h") else "1d"
        yf_range = "60d" if yf_interval == "15m" else "6mo" if yf_interval == "1h" else "1y"
        
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range={yf_range}&interval={yf_interval}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        
        try:
            async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
                res = await client.get(url, headers=headers)
                res.raise_for_status()
                result = res.json()["chart"]["result"][0]
                
                timestamps = result["timestamp"]
                quotes = result["indicators"]["quote"][0]
                
                df = pd.DataFrame({
                    "timestamp": pd.to_datetime(timestamps, unit="s", utc=True),
                    "open": quotes["open"],
                    "high": quotes["high"],
                    "low": quotes["low"],
                    "close": quotes["close"],
                    "volume": quotes.get("volume", [1000]*len(timestamps))
                }).dropna()
                
                if len(df) == 0:
                    return None
                    
                # Aceleración Polars Rust
                df = polars_engine.compute_indicators(df)
                
                self._cache[cache_key] = {
                    "df": df,
                    "price": float(df["close"].iloc[-1]),
                    "timestamp": now
                }
                self._last_fetch_ts[cache_key] = now
                return df
                
        except Exception as e:
            logger.error(f"[TRADFI_PROVIDER] Error descargando {symbol} ({ticker}): {e}")
            if cache_key in self._cache:
                return self._cache[cache_key]["df"]
            return None

    def get_latest_price(self, symbol: str) -> Optional[float]:
        """Retorna el último precio en caché para un activo TradFi."""
        for k, v in self._cache.items():
            if k.startswith(f"{symbol.upper()}:"):
                return v.get("price")
        return None

tradfi_provider = TradFiProvider()
