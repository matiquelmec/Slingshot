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
