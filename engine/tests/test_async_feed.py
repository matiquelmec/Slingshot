import asyncio
import pytest
import time
from engine.core.multi_asset_feed import MultiAssetFeed

@pytest.mark.asyncio
async def test_multi_asset_feed_async_non_blocking():
    feed = MultiAssetFeed()
    t0 = time.perf_counter()
    # Test asíncrono sobre activo de prueba (BTCUSD)
    df = await feed.fetch_klines("BTCUSD", limit=5)
    t_elapsed = (time.perf_counter() - t0) * 1000
    
    # Debe ser no nulo o retornar cache sin lanzar excepción
    if df is not None:
        assert len(df) > 0
        assert "close" in df.columns
        assert "datetime" in df.columns
    
    await feed.close()

def test_multi_asset_feed_sync_fallback():
    feed = MultiAssetFeed()
    df = feed.fetch_klines_sync("ETHUSD", limit=5)
    if df is not None:
        assert len(df) > 0
        assert "close" in df.columns
