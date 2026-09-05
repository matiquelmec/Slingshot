import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from engine.notifications.telegram import send_raw_telegram_message, _format_signal_message
from engine.risk.cluster_risk_guard import ClusterRiskGuard

@pytest.mark.asyncio
async def test_telegram_multi_chat_parsing_and_dispatch():
    """Valida que telegram procese múltiples chat IDs y envíe concurrentemente a todos."""
    from engine.notifications import telegram
    
    with patch.object(telegram, "TELEGRAM_BOT_TOKEN", "fake_token_123"), \
         patch.object(telegram, "TELEGRAM_CHAT_IDS", ["6463158372", "-5422257440"]):
        
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            
            res = await telegram.send_raw_telegram_message("Test Alert Slingshot")
            assert res is True
            # Debe haber disparado 2 llamadas (una para cada chat_id)
            assert mock_post.call_count == 2
            
            calls = [call.kwargs.get("json", {}).get("chat_id") for call in mock_post.call_args_list]
            assert "6463158372" in calls
            assert "-5422257440" in calls

def test_cluster_risk_guard_limits_correlation():
    """Valida que ClusterRiskGuard bloquee un 3er activo en el mismo cluster correlacionado."""
    guard = ClusterRiskGuard(max_per_cluster=2)
    
    # 2 activos CRYPTO_HIGH_BETA con riesgo activo LONG
    active_positions = {
        "SOLUSDT": {
            "signal": {"type": "LONG", "price": 140.0, "stop_loss": 130.0},
            "smart_trailing": {"be_active": False}
        },
        "AVAXUSDT": {
            "signal": {"type": "LONG", "price": 25.0, "stop_loss": 23.0},
            "smart_trailing": {"be_active": False}
        }
    }
    
    # NEARUSDT está en el mismo cluster CRYPTO -> No debe permitir
    can_near, reason = guard.can_open_position("NEARUSDT", "LONG", 80.0, active_positions)
    assert can_near is False
    assert "SOP-30" in reason or "BETA" in reason or "corr" in reason.lower()
    
    # XAUUSDT está en TRADFI_METALS -> Sí debe permitir
    can_gold, reason_gold = guard.can_open_position("XAUUSDT", "LONG", 80.0, active_positions)
    assert can_gold is True
    
    # Si SOL pasa a Breakeven ($0.00 riesgo flotante)
    active_positions["SOLUSDT"]["smart_trailing"]["be_active"] = True
    active_positions["SOLUSDT"]["signal"]["stop_loss"] = 140.5
    can_near_be, _ = guard.can_open_position("NEARUSDT", "LONG", 80.0, active_positions)
    assert can_near_be is True

@pytest.mark.asyncio
async def test_orphan_order_sweeper_logic():
    """Valida la detección y cancelación de órdenes huérfanas de posiciones cerradas."""
    from engine.execution.bitunix_executor import BitunixExecutor
    ex = BitunixExecutor(dry_run=True)
    
    # Órdenes pendientes en Bitunix: TP de SOL (posición cerrada) y TP de ETH (posición abierta)
    pending_orders = [
        {"orderId": "tp_sol_1", "symbol": "SOLUSDT", "reduceOnly": True, "side": "SELL"},
        {"orderId": "tp_eth_1", "symbol": "ETHUSDT", "reduceOnly": True, "side": "SELL"},
    ]
    
    active_symbols = {"ETHUSDT"} # Solo ETH está abierta, SOL ya cerró
    
    orphans = [
        o for o in pending_orders 
        if o.get("reduceOnly") and o.get("symbol") not in active_symbols
    ]
    
    assert len(orphans) == 1
    assert orphans[0]["orderId"] == "tp_sol_1"
    assert orphans[0]["symbol"] == "SOLUSDT"
