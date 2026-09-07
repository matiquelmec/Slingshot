"""
engine/indicators/tradfi_provider.py — Proveedor de Datos TradFi Multi-Mercado v51.0
==================================================================================
Descarga y gestiona velas e indicadores en tiempo real para activos de MetaTrader 5 / FTMO:
- XAUUSD (Gold Spot - Long Only)
- US100 (Nasdaq 100 Cash)
- GBPUSD (Forex Cable)
- US30 (Dow Jones 30 Cash)
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
        "point_size": 0.01,
        "tier": "TIER_A",
        "enabled": True,
        "long_only": True
    },
    "US100": {
        "ticker": "NQ=F",
        "name": "Nasdaq 100 Cash",
        "category": "INDICES",
        "contract_size": 1,
        "spread_usd": 1.10,
        "min_lot": 0.1,
        "pip_value": 1.0,
        "point_size": 0.25,
        "tier": "TIER_A",
        "enabled": True,
        "long_only": False
    },
    "GBPUSD": {
        "ticker": "GBPUSD=X",
        "name": "GBP/USD Forex",
        "category": "FOREX",
        "contract_size": 100000,
        "spread_usd": 0.00005,
        "min_lot": 0.01,
        "pip_value": 10.0,
        "point_size": 0.0001,
        "tier": "TIER_A",
        "enabled": True,
        "long_only": False
    },
    "US30": {
        "ticker": "YM=F",
        "name": "Dow Jones 30 Cash",
        "category": "INDICES",
        "contract_size": 1,
        "spread_usd": 2.20,
        "min_lot": 0.1,
        "pip_value": 1.0,
        "point_size": 1.0,
        "tier": "TIER_A",
        "enabled": True,
        "long_only": False
    },
    "EURUSD": {
        "ticker": "EURUSD=X",
        "name": "EUR/USD Forex",
        "category": "FOREX",
        "contract_size": 100000,
        "spread_usd": 0.00002,
        "min_lot": 0.01,
        "pip_value": 10.0,
        "point_size": 0.00001,
        "tier": "TIER_B",
        "enabled": False,
        "long_only": False
    },
    "GBPJPY": {
        "ticker": "GBPJPY=X",
        "name": "GBP/JPY Dragon",
        "category": "FOREX",
        "contract_size": 100000,
        "spread_usd": 0.025,
        "min_lot": 0.01,
        "pip_value": 6.8,
        "point_size": 0.01,
        "tier": "TIER_B",
        "enabled": False,
        "long_only": False
    },
    "US500": {
        "ticker": "ES=F",
        "name": "SP500 Cash",
        "category": "INDICES",
        "contract_size": 1,
        "spread_usd": 0.40,
        "min_lot": 0.1,
        "pip_value": 1.0,
        "point_size": 0.25,
        "tier": "EXCLUDED",
        "enabled": False,
        "long_only": False
    },
    "HGUSD": {
        "ticker": "HG=F",
        "name": "Copper High Grade",
        "category": "COMMODITIES",
        "contract_size": 25000,
        "spread_usd": 0.0010,
        "min_lot": 0.01,
        "pip_value": 12.5,
        "point_size": 0.0005,
        "tier": "EXCLUDED",
        "enabled": False,
        "long_only": False
    },
    "GER40": {
        "ticker": "^GDAXI",
        "name": "DAX 40 Germany",
        "category": "INDICES",
        "contract_size": 25,
        "spread_usd": 1.50,
        "min_lot": 0.1,
        "pip_value": 1.0,
        "point_size": 1.0,
        "tier": "EXCLUDED",
        "enabled": False,
        "long_only": False
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

        # [SOP-66 NATIVE MT5 DATA FEED] Prioridad: Alimentacion Directa desde MetaTrader 5 (FTMO)
        try:
            from engine.execution.mt5_bridge import mt5_bridge
            import MetaTrader5 as mt5
            
            if mt5_bridge.connected:
                sym_mt5 = symbol.replace("USDT", "USD")
                if ".cash" not in sym_mt5 and any(idx in sym_mt5 for idx in ["US100", "US30", "US500", "GER40"]):
                    sym_mt5 = f"{sym_mt5}.cash"
                    
                tf_map = {
                    "1m": mt5.TIMEFRAME_M1,
                    "5m": mt5.TIMEFRAME_M5,
                    "15m": mt5.TIMEFRAME_M15,
                    "1h": mt5.TIMEFRAME_H1,
                    "4h": mt5.TIMEFRAME_H4,
                    "1d": mt5.TIMEFRAME_D1
                }
                mt5_tf = tf_map.get(interval, mt5.TIMEFRAME_M15)
                mt5.symbol_select(sym_mt5, True)
                rates = mt5.copy_rates_from_pos(sym_mt5, mt5_tf, 0, limit)
                
                if rates is not None and len(rates) > 20:
                    df = pd.DataFrame(rates)
                    df["timestamp"] = pd.to_datetime(df["time"], unit="s", utc=True)
                    df.rename(columns={"tick_volume": "volume"}, inplace=True)
                    df = df[["timestamp", "open", "high", "low", "close", "volume"]]
                    
                    df_calc = polars_engine.compute_indicators_df(df)
                    self._cache[cache_key] = {"df": df_calc, "source": "MT5_NATIVE"}
                    self._last_fetch_ts[cache_key] = now
                    return df_calc
        except Exception as mt5_err:
            logger.debug(f"[TRADFI_PROVIDER] Fallback de MT5 a Yahoo Finance para {symbol}: {mt5_err}")

        # Fallback de Alta Disponibilidad: Yahoo Finance REST API v8
        try:
            range_map = {"15m": "5d", "1h": "1mo", "4h": "3mo", "1d": "1y"}
            yf_range = range_map.get(interval, "5d")
            
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range={yf_range}&interval={interval}"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            
            async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
                res = await client.get(url, headers=headers)
                res.raise_for_status()
                data = res.json()
                
                chart_data = data["chart"]["result"][0]
                timestamps = chart_data["timestamp"]
                quotes = chart_data["indicators"]["quote"][0]
                
                df = pd.DataFrame({
                    "timestamp": pd.to_datetime(timestamps, unit="s", utc=True),
                    "open": quotes["open"],
                    "high": quotes["high"],
                    "low": quotes["low"],
                    "close": quotes["close"],
                    "volume": quotes.get("volume", [1.0] * len(timestamps))
                }).dropna()
                
                df_calc = polars_engine.compute_indicators_df(df)
                self._cache[cache_key] = {"df": df_calc, "source": "YAHOO_REST"}
                self._last_fetch_ts[cache_key] = now
                return df_calc
                
        except Exception as e:
            logger.error(f"[TRADFI_PROVIDER] Error descargando {symbol} ({ticker}) en {interval}: {e}")
            return None

tradfi_provider = TradFiProvider()
