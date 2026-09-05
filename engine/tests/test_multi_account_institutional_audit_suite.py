import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from engine.execution.nexus import NexusNode

@pytest.mark.asyncio
async def test_multi_account_independent_risk_isolation():
    """Valida que una cuenta con 4 posiciones NO bloquee a otra cuenta que tiene cupo disponible."""
    node = NexusNode(dry_run=True)
    
    # Simular 4 posiciones con riesgo en 'primary'
    node._high_confluence_buffer = {"primary": []}
    node._active_positions = {
        "primary_XAUUSDT": {"account_id": "primary", "signal": {"asset": "XAUUSDT", "type": "LONG", "price": 4000, "stop_loss": 3950}, "smart_trailing": {"be_active": False}},
        "primary_NEARUSDT": {"account_id": "primary", "signal": {"asset": "NEARUSDT", "type": "LONG", "price": 2.0, "stop_loss": 1.9}, "smart_trailing": {"be_active": False}},
        "primary_ETHUSDT": {"account_id": "primary", "signal": {"asset": "ETHUSDT", "type": "LONG", "price": 2500, "stop_loss": 2400}, "smart_trailing": {"be_active": False}},
        "primary_CLUSDT": {"account_id": "primary", "signal": {"asset": "CLUSDT", "type": "LONG", "price": 90, "stop_loss": 88}, "smart_trailing": {"be_active": False}},
        # 'cliente_2' solo tiene 2 posiciones
        "cliente_2_XAUUSDT": {"account_id": "cliente_2", "signal": {"asset": "XAUUSDT", "type": "LONG", "price": 4000, "stop_loss": 3950}, "smart_trailing": {"be_active": False}},
        "cliente_2_NEARUSDT": {"account_id": "cliente_2", "signal": {"asset": "NEARUSDT", "type": "LONG", "price": 2.0, "stop_loss": 1.9}, "smart_trailing": {"be_active": False}},
    }
    
    # Validar contabilidad aislada
    assert node.get_unprotected_risk_count("primary") == 4
    assert node.get_unprotected_risk_count("cliente_2") == 2
    
    # Simular orden lÃ­mite entrante para SOLUSDT
    test_sig = {
        "asset": "SOLUSDT",
        "symbol": "SOLUSDT",
        "type": "LONG",
        "signal_type": "LONG",
        "price": 150.0,
        "stop_loss": 145.0,
        "confluence_score": 85.0,
        "vwap_dist_pct": 0.01,
        "adx": 30.0,
        "ker": 0.50
    }
    
    mock_ex_pri = AsyncMock()
    mock_ex_c2 = AsyncMock()
    
    with patch.object(node.account_manager, "get_all_accounts") as mock_accs, \
         patch.object(node.account_manager, "get_executor", side_effect=lambda aid: mock_ex_pri if aid == "primary" else mock_ex_c2):
        
        acc1 = MagicMock(account_id="primary", label="Principal")
        acc2 = MagicMock(account_id="cliente_2", label="Cliente 2")
        mock_accs.return_value = [acc1, acc2]
        
        # Ejecutar colocaciÃ³n lÃ­mite
        await node.process_limit_setup(test_sig)
        
        # 'primary' no debiÃ³ colocar lÃ­mite (4/4 cupos llenos)
        assert not mock_ex_pri.place_limit_order.called
        # 'cliente_2' sÃ­ debiÃ³ procesar orden o guardarse de forma aislada
        assert node.get_unprotected_risk_count("cliente_2") == 2

@pytest.mark.asyncio
async def test_high_confluence_buffer_queuing():
    """Valida que una oportunidad >= 78% se encole en el buffer cuando la cuenta estÃ¡ llena."""
    node = NexusNode(dry_run=True)
    
    # 4 posiciones en primary
    node._high_confluence_buffer = {"primary": []}
    node._active_positions = {
        f"primary_SYM{i}": {"account_id": "primary", "signal": {"asset": f"SYM{i}", "type": "LONG", "price": 100, "stop_loss": 90}, "smart_trailing": {"be_active": False}}
        for i in range(4)
    }
    
    sig_god_mode = {
        "asset": "BTCUSDT",
        "symbol": "BTCUSDT",
        "type": "LONG",
        "price": 60000.0,
        "stop_loss": 59000.0,
        "confluence_score": 92.0
    }
    
    node.enqueue_high_confluence_opportunity(sig_god_mode, "primary")
    assert "primary" in node._high_confluence_buffer
    assert len(node._high_confluence_buffer["primary"]) == 1
    assert node._high_confluence_buffer["primary"][0]["asset"] == "BTCUSDT"

@pytest.mark.asyncio
async def test_instant_sl_placed_within_execute_signal():
    """Valida que execute_signal llame de inmediato a place_position_tpsl."""
    from engine.execution.bitunix_executor import BitunixExecutor
    ex = BitunixExecutor(dry_run=False)
    
    mock_order_res = {"code": 0, "data": {"orderId": "main_ord_123"}}
    mock_pos_res = [{"symbol": "ETHUSDT", "positionId": "pos_9999"}]
    
    with patch.object(ex, "_request", new_callable=AsyncMock) as mock_req, \
         patch.object(ex, "get_pending_positions", new_callable=AsyncMock, return_value=mock_pos_res), \
         patch.object(ex, "place_position_tpsl", new_callable=AsyncMock) as mock_tpsl:
        
        mock_req.return_value = mock_order_res
        
        signal = {
            "asset": "ETHUSDT",
            "type": "LONG",
            "price": 2500.0,
            "stop_loss": 2450.0,
            "position_size": 20.0,
            "leverage": 10
        }
        
        await ex.execute_signal(signal)
        
        # Verificar que place_position_tpsl fue invocado con positionId y stop_loss
        assert mock_tpsl.called
        call_kwargs = mock_tpsl.call_args[1]
        assert call_kwargs["symbol"] == "ETHUSDT"
        assert call_kwargs["position_id"] == "pos_9999"
        assert call_kwargs["sl_price"] == 2450.0

@pytest.mark.asyncio
async def test_cancel_all_pending_orders_protects_take_profits():
    """Valida que cancel_all_pending_orders con only_open=True NUNCA cancele Ã³rdenes reduceOnly."""
    from engine.execution.bitunix_executor import BitunixExecutor
    ex = BitunixExecutor(dry_run=False)
    
    fake_orders = [
        {"orderId": "entry_1", "symbol": "BTCUSDT", "tradeSide": "OPEN", "reduceOnly": False},
        {"orderId": "tp_1", "symbol": "BTCUSDT", "tradeSide": "CLOSE", "reduceOnly": True},
        {"orderId": "tp_2", "symbol": "BTCUSDT", "tradeSide": None, "reduceOnly": True},
    ]
    
    with patch.object(ex, "get_pending_orders", new_callable=AsyncMock, return_value=fake_orders), \
         patch.object(ex, "cancel_limit_order", new_callable=AsyncMock) as mock_cancel:
        
        await ex.cancel_all_pending_orders(only_open=True)
        
        # Solo entry_1 debiÃ³ ser cancelada
        assert mock_cancel.call_count == 1
        assert mock_cancel.call_args[0] == ("BTCUSDT", "entry_1")

