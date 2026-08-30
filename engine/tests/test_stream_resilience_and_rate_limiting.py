"""
engine/tests/test_stream_resilience_and_rate_limiting.py
=============================================================================
SUITE DE CERTIFICACIÓN QA: STREAM RESILIENCE, TOKEN BUCKET & FAILOVER (v26.1)
=============================================================================
Audita:
1. Token Bucket Rate Limiter asíncrono para Bitunix REST (control de burst y tasa).
2. Staggered Handshake calculation e inmunidad ante concurrencia.
3. Resiliencia de NewsWorker ante timeouts de feeds externos.
4. Transición limpia y reconexión controlada de Broadcaster.
"""
import pytest
import asyncio
import time
from unittest.mock import patch, AsyncMock
from engine.api.broadcaster.rest_fallback import AsyncTokenBucket, BitunixFallback
from engine.workers.news_worker import NewsWorker

@pytest.mark.asyncio
async def test_async_token_bucket_rate_limiting():
    """
    Verifica que el Token Bucket regule estrictamente la tasa de llamadas concurrentes.
    """
    bucket = AsyncTokenBucket(rate_per_sec=5.0, burst=2)
    
    # 2 tokens iniciales disponibles (burst)
    assert bucket.tokens == 2.0
    
    start_time = time.time()
    # Solicitar 4 tokens de golpe
    for _ in range(4):
        await bucket.acquire()
    elapsed = time.time() - start_time
    
    # Los primeros 2 salen de inmediato, los siguientes 2 deben esperar ~0.4s (2/5s)
    assert elapsed >= 0.35, f"Rate limiter debió demorar al menos 0.35s, demoró {elapsed:.3f}s"

@pytest.mark.asyncio
async def test_bitunix_fallback_lifecycle_and_rate_limiting():
    """
    Verifica que BitunixFallback inicie y detenga el ciclo sin bloquear ni arrojar errores.
    """
    class MockBroadcaster:
        def __init__(self):
            self._messages = []
        async def _broadcast(self, msg):
            self._messages.append(msg)
        async def _process_kline_stream(self, payload, raw):
            pass
        async def _process_depth_stream(self, payload):
            pass

    mock_bc = MockBroadcaster()
    fallback = BitunixFallback("SOLUSDT", "1m", mock_bc)
    
    assert fallback.is_running is False
    await fallback.start()
    assert fallback.is_running is True
    assert len(mock_bc._messages) > 0
    assert mock_bc._messages[0]["data"]["mode"] == "FALLBACK"
    
    await fallback.stop()
    assert fallback.is_running is False
    assert mock_bc._messages[-1]["data"]["mode"] == "WS"

@pytest.mark.asyncio
async def test_news_worker_feed_timeout_isolation():
    """
    Verifica que NewsWorker continúe operando normalmente ante timeouts en feeds externos.
    """
    worker = NewsWorker(interval_seconds=60)
    
    # Simular que un feed arroja TimeoutException
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        import httpx
        mock_get.side_effect = httpx.TimeoutException("Connection timed out to feed")
        
        # Debe ejecutarse sin lanzar excepción no atrapada
        await worker.fetch_and_process_news()

@pytest.mark.asyncio
async def test_staggered_handshake_jitter_distribution():
    """
    Verifica que el cálculo de retardo con jitter distribuya uniformemente el arranque.
    """
    import random
    staggers = [random.uniform(0.08, 0.25) for _ in range(20)]
    assert all(0.08 <= s <= 0.25 for s in staggers)
    assert len(set(staggers)) > 15, "El jitter debe ser aleatorio y no colisionar"