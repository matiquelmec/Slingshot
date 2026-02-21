import httpx
import pandas as pd
from typing import Optional, List
from ..api.config import settings

class DataFetcher:
    """Fetcher de datos OHLCV con sistema de fallbacks (4-tier)."""
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=10.0)

    async def fetch_binance(self, symbol: str, interval: str = "1h", limit: int = 100) -> Optional[pd.DataFrame]:
        """Tier 1: Binance REST API."""
        url = f"https://api.binance.com/api/v3/klines"
        params = {
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": limit
        }
        try:
            response = await self.client.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                df = pd.DataFrame(data, columns=[
                    'timestamp', 'open', 'high', 'low', 'close', 'volume',
                    'close_time', 'quote_asset_volume', 'number_of_trades',
                    'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
                ])
                # Convertimos el tiempo Unix (ms) a Datetime y lo forzamos a ser UTC-aware
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = df[col].astype(float)
                return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        except Exception as e:
            print(f"Binance fetch error: {e}")
        return None

    async def fetch_coingecko(self, coin_id: str, days: int = 1) -> Optional[pd.DataFrame]:
        """Tier 2: CoinGecko (Fallback)."""
        # Implementación simplificada
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc"
        params = {"vs_currency": "usd", "days": days}
        try:
            response = await self.client.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close'])
                # Convertimos el tiempo Unix (ms) a Datetime y lo forzamos a ser UTC-aware
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
                df['volume'] = 0.0 # CG OHLC no da volumen directamente en este endpoint
                return df
        except Exception as e:
            print(f"CoinGecko fetch error: {e}")
        return None

    async def get_ohlcv(self, symbol: str, interval: str = "1h", limit: int = 100, coingecko_id: str = "bitcoin") -> pd.DataFrame:
        """Intenta obtener datos pasando por los niveles de fallback."""
        # Tier 1
        df = await self.fetch_binance(symbol, interval=interval, limit=limit)
        if df is not None: return df
        
        # Tier 2
        df = await self.fetch_coingecko(coingecko_id)
        if df is not None: return df
        
        # Throw error or return empty if all fail
        raise Exception(f"Failed to fetch data for {symbol} from all tiers.")

fetcher = DataFetcher()
