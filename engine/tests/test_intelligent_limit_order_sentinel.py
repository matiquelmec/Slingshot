"""
engine/tests/test_intelligent_limit_order_sentinel.py
=============================================================================
SUITE DE PRUEBAS UNITARIAS: CENTINELA INTELIGENTE DE ÓRDENES LÍMITE (v22.0)
=============================================================================
"""
import pytest
import asyncio
import time
from unittest.mock import AsyncMock, patch, MagicMock

from engine.workers.trade_manager import TradeManager
from engine.execution.bitunix_executor import BitunixExecutor
from engine.execution.nexus import NexusNode


@pytest.mark.asyncio
async def test_sentinel_cancels_when_target_missed_long():
    """Verifica que el centinela auto-cancele una orden límite LONG si el precio toca TP1 sin entrar."""
    tm = TradeManager()
    
    mock_pending_orders = [{
        "orderId": "mock_limit_eth_1",
        "symbol": "ETHUSDT",
        "side": "BUY",
        "price": "2400.00",
        "slPrice": "2360.00",
        "tradeSide": "OPEN",
        "orderType": "LIMIT",
        "reduceOnly": False,
        "ctime": str(int(time.time() * 1000) - 1000)
    }]

    with patch("engine.execution.bitunix_executor.BitunixExecutor.get_pending_orders", new_callable=AsyncMock) as mock_get_orders, \
         patch("engine.execution.bitunix_executor.BitunixExecutor.get_ticker_price", new_callable=AsyncMock) as mock_price, \
         patch("engine.execution.bitunix_executor.BitunixExecutor.cancel_limit_order", new_callable=AsyncMock) as mock_cancel, \
         patch("engine.execution.nexus.nexus.get_unprotected_risk_count", return_value=1), \
         patch("engine.execution.nexus.nexus.remove_pending_limit_symbol") as mock_remove_sym:

        mock_get_orders.return_value = mock_pending_orders
        # El precio se escapó a $2460 (superando el TP1 de ~$2452) sin retroceder a $2400
        mock_price.return_value = 2465.00
        mock_cancel.return_value = True

        cancelled = await tm.sync_live_bitunix_pending_orders()

        assert len(cancelled) == 1
        assert cancelled[0]["symbol"] == "ETHUSDT"
        assert "MISSED_TARGET" in cancelled[0]["reason"]
        mock_cancel.assert_called_once_with("ETHUSDT", "mock_limit_eth_1")
        mock_remove_sym.assert_called_once_with("ETHUSDT")


@pytest.mark.asyncio
async def test_sentinel_cancels_when_target_missed_short():
    """Verifica que el centinela auto-cancele una orden límite SHORT si el precio toca TP1 bajista sin entrar."""
    tm = TradeManager()
    
    mock_pending_orders = [{
        "orderId": "mock_limit_sol_short",
        "symbol": "SOLUSDT",
        "side": "SELL",
        "price": "100.00",
        "slPrice": "104.00",
        "tradeSide": "OPEN",
        "orderType": "LIMIT",
        "reduceOnly": False,
        "ctime": str(int(time.time() * 1000) - 1000)
    }]

    with patch("engine.execution.bitunix_executor.BitunixExecutor.get_pending_orders", new_callable=AsyncMock) as mock_get_orders, \
         patch("engine.execution.bitunix_executor.BitunixExecutor.get_ticker_price", new_callable=AsyncMock) as mock_price, \
         patch("engine.execution.bitunix_executor.BitunixExecutor.cancel_limit_order", new_callable=AsyncMock) as mock_cancel, \
         patch("engine.execution.nexus.nexus.get_unprotected_risk_count", return_value=1), \
         patch("engine.execution.nexus.nexus.remove_pending_limit_symbol"):

        mock_get_orders.return_value = mock_pending_orders
        # Precio se desplomó a $94.00 (alcanzando el TP1 de $94.80) sin subir a la entrada de $100
        mock_price.return_value = 93.50
        mock_cancel.return_value = True

        cancelled = await tm.sync_live_bitunix_pending_orders()

        assert len(cancelled) == 1
        assert "MISSED_TARGET" in cancelled[0]["reason"]
        mock_cancel.assert_called_once_with("SOLUSDT", "mock_limit_sol_short")


@pytest.mark.asyncio
async def test_sentinel_cancels_when_sl_breached_prior_to_fill():
    """Verifica que el centinela auto-cancele si el precio perfora el Stop Loss antes de entrar."""
    tm = TradeManager()
    
    mock_pending_orders = [{
        "orderId": "mock_limit_link_1",
        "symbol": "LINKUSDT",
        "side": "BUY",
        "price": "11.00",
        "slPrice": "10.50",
        "tradeSide": "OPEN",
        "orderType": "LIMIT",
        "reduceOnly": False,
        "ctime": str(int(time.time() * 1000) - 1000)
    }]

    with patch("engine.execution.bitunix_executor.BitunixExecutor.get_pending_orders", new_callable=AsyncMock) as mock_get_orders, \
         patch("engine.execution.bitunix_executor.BitunixExecutor.get_ticker_price", new_callable=AsyncMock) as mock_price, \
         patch("engine.execution.bitunix_executor.BitunixExecutor.cancel_limit_order", new_callable=AsyncMock) as mock_cancel, \
         patch("engine.execution.nexus.nexus.get_unprotected_risk_count", return_value=1), \
         patch("engine.execution.nexus.nexus.remove_pending_limit_symbol"):

        mock_get_orders.return_value = mock_pending_orders
        # Caída abrupta perforando el SL a $10.40
        mock_price.return_value = 10.40
        mock_cancel.return_value = True

        cancelled = await tm.sync_live_bitunix_pending_orders()

        assert len(cancelled) == 1
        assert "PRE_ENTRY_SL_BREACH" in cancelled[0]["reason"]
        mock_cancel.assert_called_once_with("LINKUSDT", "mock_limit_link_1")


@pytest.mark.asyncio
async def test_sentinel_cancels_on_ttl_expiration():
    """Verifica que el centinela expire órdenes límite antiguas (>3.5 horas) con precio desfasado."""
    tm = TradeManager()
    
    # Orden creada hace 4 horas (14,400 segundos)
    old_ctime_ms = int(time.time() * 1000) - (14400 * 1000)
    
    mock_pending_orders = [{
        "orderId": "mock_limit_render_old",
        "symbol": "RENDERUSDT",
        "side": "BUY",
        "price": "1.40",
        "slPrice": "1.35",
        "tradeSide": "OPEN",
        "orderType": "LIMIT",
        "reduceOnly": False,
        "ctime": str(old_ctime_ms)
    }]

    with patch("engine.execution.bitunix_executor.BitunixExecutor.get_pending_orders", new_callable=AsyncMock) as mock_get_orders, \
         patch("engine.execution.bitunix_executor.BitunixExecutor.get_ticker_price", new_callable=AsyncMock) as mock_price, \
         patch("engine.execution.bitunix_executor.BitunixExecutor.cancel_limit_order", new_callable=AsyncMock) as mock_cancel, \
         patch("engine.execution.nexus.nexus.get_unprotected_risk_count", return_value=1), \
         patch("engine.execution.nexus.nexus.remove_pending_limit_symbol"):

        mock_get_orders.return_value = mock_pending_orders
        # Precio actual a $1.44 (desfasado > 1.5% de la entrada de $1.40)
        mock_price.return_value = 1.44
        mock_cancel.return_value = True

        cancelled = await tm.sync_live_bitunix_pending_orders()

        assert len(cancelled) == 1
        assert "TTL_EXPIRED" in cancelled[0]["reason"]
        mock_cancel.assert_called_once_with("RENDERUSDT", "mock_limit_render_old")


@pytest.mark.asyncio
async def test_sentinel_purges_limits_when_max_risk_slots_filled():
    """Verifica que el centinela ejecute purga de órdenes límite si ya hay 4 posiciones abiertas en riesgo."""
    tm = TradeManager()

    with patch("engine.execution.nexus.nexus.get_unprotected_risk_count", return_value=4), \
         patch("engine.execution.nexus.nexus.purge_all_pending_limit_orders", new_callable=AsyncMock) as mock_purge:

        cancelled = await tm.sync_live_bitunix_pending_orders()

        assert cancelled == []
        mock_purge.assert_called_once_with(reason="MAX_4_RISK_SLOTS_REACHED")


@pytest.mark.asyncio
async def test_sentinel_preserves_valid_pending_orders_in_discount():
    """Verifica que las órdenes válidas que esperan en zona de descuento no sean canceladas."""
    tm = TradeManager()
    
    mock_pending_orders = [{
        "orderId": "mock_limit_near_valid",
        "symbol": "NEARUSDT",
        "side": "BUY",
        "price": "2.50",
        "slPrice": "2.40",
        "tradeSide": "OPEN",
        "orderType": "LIMIT",
        "reduceOnly": False,
        "ctime": str(int(time.time() * 1000) - 300000) # Creada hace 5 minutos
    }]

    with patch("engine.execution.bitunix_executor.BitunixExecutor.get_pending_orders", new_callable=AsyncMock) as mock_get_orders, \
         patch("engine.execution.bitunix_executor.BitunixExecutor.get_ticker_price", new_callable=AsyncMock) as mock_price, \
         patch("engine.execution.bitunix_executor.BitunixExecutor.cancel_limit_order", new_callable=AsyncMock) as mock_cancel, \
         patch("engine.execution.nexus.nexus.get_unprotected_risk_count", return_value=1):

        mock_get_orders.return_value = mock_pending_orders
        # Precio actual a $2.52 (acercándose a la entrada $2.50 sin tocar TP1 ni SL)
        mock_price.return_value = 2.52

        cancelled = await tm.sync_live_bitunix_pending_orders()

        assert len(cancelled) == 0
        mock_cancel.assert_not_called()
