import pytest
from unittest.mock import patch, AsyncMock
from engine.router.telegram_dispatcher import TelegramDispatcher

@pytest.mark.asyncio
async def test_telegram_lifecycle_suppresses_already_active_position():
    dispatcher = TelegramDispatcher()
    dispatcher.enabled = True
    dispatcher.bot_token = "mock_token"
    dispatcher.chat_ids = ["123456"]

    signal = {
        "asset": "NEARUSDT",
        "symbol": "NEARUSDT",
        "signal_type": "LONG",
        "price": 2.37,
        "stop_loss": 2.31,
        "confluence_score": 85,
        "is_test": False
    }

    mock_active = {
        "primary_NEARUSDT": {
            "signal": {"asset": "NEARUSDT"}
        }
    }

    with patch("engine.execution.nexus.nexus._active_positions", mock_active), \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        
        sent = await dispatcher.send_signal_alert(signal)
        assert sent is False
        mock_post.assert_not_called()

@pytest.mark.asyncio
async def test_telegram_lifecycle_milestone_methods():
    dispatcher = TelegramDispatcher()
    dispatcher.enabled = True
    dispatcher.bot_token = "mock_token"
    dispatcher.chat_ids = ["123456"]

    with patch.object(dispatcher, "send_raw_message", new_callable=AsyncMock) as mock_raw:
        mock_raw.return_value = True

        # Test fill alert
        res_fill = await dispatcher.send_trade_fill_alert("NEARUSDT", "BUY", 2.372, 31, "Primary")
        assert res_fill is True
        assert "ORDEN EJECUTADA" in mock_raw.call_args[0][0]

        # Test TP hit alert
        res_tp = await dispatcher.send_tp_hit_alert("NEARUSDT", "TP1 (60%)", 2.460, 2.75, is_be=True)
        assert res_tp is True
        assert "HIT TP" in mock_raw.call_args[0][0]
        assert "BREAKEVEN" in mock_raw.call_args[0][0]

        # Test closed alert
        res_close = await dispatcher.send_trade_closed_alert("NEARUSDT", "TP3_HIT", 2.670, 12.40, pnl_r=5.0)
        assert res_close is True
        assert "TRADE CERRADO" in mock_raw.call_args[0][0]

@pytest.mark.asyncio
async def test_fresh_execution_dispatches_with_badge_without_self_suppression():
    """
    TEST CRÍTICO: Valida que si la orden fue recién colocada en Bitunix
    (execution_status={'placed': True, 'order_id': 'bitunix_12345'}),
    Telegram NO la auto-suprima aunque el símbolo ya esté en _pending_limit_symbols.
    """
    dispatcher = TelegramDispatcher()
    dispatcher.enabled = True
    dispatcher.bot_token = "mock_token"
    dispatcher.chat_ids = ["123456"]

    signal = {
        "asset": "BTCUSDT",
        "symbol": "BTCUSDT",
        "signal_type": "LONG",
        "price": 65000.0,
        "stop_loss": 64000.0,
        "confluence_score": 85,
        "is_test": False,
        "execution_status": {
            "placed": True,
            "order_id": "999888777",
            "status": "ORDER_PLACED"
        }
    }

    from unittest.mock import MagicMock
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    # Simular que Nexus ya tiene a BTCUSDT en pending limits
    with patch("engine.execution.nexus.nexus._pending_limit_symbols", {"BTCUSDT"}), \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post, \
         patch.object(dispatcher._vault, "is_signal_in_cooldown", return_value=(False, 0, 0.0)):
        
        mock_post.return_value = mock_resp
        sent = await dispatcher.send_signal_alert(signal)
        assert sent is True
        assert mock_post.called
        # Verificar que el mensaje enviado incluye la confirmación de Bitunix
        called_payload = mock_post.call_args[1]["json"]
        assert "ORDEN LÍMITE ACTIVA EN BITUNIX" in called_payload["text"]
        assert "999888777" in called_payload["text"]
