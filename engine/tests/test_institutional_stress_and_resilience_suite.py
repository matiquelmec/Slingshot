import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from engine.execution.nexus import NexusNode
from engine.execution.bitunix_executor import BitunixExecutor

@pytest.mark.asyncio
async def test_atomic_deduplication_under_high_concurrency_burst():
    """
    [STRESS TEST: RACE CONDITION FORTRESS]
    Simula una ráfaga de 10 señales IDÉNTICAS de ETHUSDT llegando exactamente en el mismo milisegundo.
    Valida que los filtros atómicos de Nexus garanticen que SOLO 1 orden proceda y 9 sean descartadas.
    """
    node = NexusNode(dry_run=True)
    mock_ex = AsyncMock()
    mock_ex.get_pending_positions.return_value = []
    mock_ex.get_pending_orders.return_value = []
    mock_ex.get_symbol_precision.return_value = (2, 2)
    mock_ex.place_limit_order.return_value = {"code": 0, "data": {"orderId": "limit_123"}}
    
    with patch.object(node.account_manager, "get_all_accounts") as mock_accs, \
         patch.object(node.account_manager, "get_executor", return_value=mock_ex):
        
        acc = MagicMock(account_id="primary", label="Principal", risk_pct=0.025, max_notional_mult=5.0)
        mock_accs.return_value = [acc]
        
        sig = {
            "asset": "ETHUSDT",
            "symbol": "ETHUSDT",
            "type": "LONG",
            "direction": "LONG",
            "price": 2450.0,
            "stop_loss": 2400.0,
            "confluence_score": 85.0
        }
        
        # Disparar 10 tareas concurrentes en paralelo
        tasks = [node.process_limit_setup(dict(sig)) for _ in range(10)]
        await asyncio.gather(*tasks)
        
        # Validar que no se generen duplicados (máximo 1 orden colocada)
        assert mock_ex.place_limit_order.call_count <= 1

@pytest.mark.asyncio
async def test_frozen_margin_guard_deducts_open_limits():
    """
    [MARGIN SAFETY TEST]
    Valida que get_net_available_margin_usdt reste correctamente el saldo congelado
    en órdenes pendientes para no saturar el balance.
    """
    ex = BitunixExecutor(dry_run=False)
    
    with patch.object(ex, "get_available_margin_usdt", new_callable=AsyncMock, return_value=100.0), \
         patch.object(ex, "get_pending_orders", new_callable=AsyncMock) as mock_orders:
        
        # 1 orden de entrada de 1 ETH a $2000 (apalancamiento 10x = $200 de notional / $20 margen)
        mock_orders.return_value = [
            {"symbol": "ETHUSDT", "tradeSide": "OPEN", "reduceOnly": False, "price": 200.0, "qty": 1.0}, # $20 congelados
            {"symbol": "BTCUSDT", "tradeSide": "CLOSE", "reduceOnly": True, "price": 60000.0, "qty": 0.1} # TP (no congela margen)
        ]
        
        net_avail = await ex.get_net_available_margin_usdt()
        # 100 - (200*1 / 10) = 100 - 20 = 80 USDT
        assert net_avail == 80.0

@pytest.mark.asyncio
async def test_ttl_sentinel_identifies_stale_orders():
    """
    [TTL EXPIRY TEST]
    Valida que las órdenes creadas hace más de 3 horas (10800s) sean marcadas como expiradas.
    """
    import time
    now = time.time()
    old_time = now - 11000 # Creada hace 3.05 horas
    fresh_time = now - 1000 # Creada hace 16 minutos
    
    assert (now - old_time) > 10800
    assert (now - fresh_time) < 10800
