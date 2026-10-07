"""
SOP-120: Anti-Spam Gate del TelegramDispatcher.
Verifica que eventos repetidos (cada ciclo de 15s del reconciliador) se envíen una sola vez.
"""
import pytest
from unittest.mock import AsyncMock, patch

import engine.router.telegram_dispatcher as td


@pytest.fixture
def dispatcher(tmp_path, monkeypatch):
    monkeypatch.setattr(td, "_STATE_FILE", tmp_path / "telegram_sent_state.json")
    d = td.TelegramDispatcher()
    d.enabled = True
    d._sent_state = {}
    d.send_raw_message = AsyncMock(return_value=True)
    return d


async def test_unauthorized_alert_sent_once_across_cycles(dispatcher):
    for _ in range(10):  # 10 ciclos del reconciliador
        await dispatcher.send_unauthorized_position_alert("FARTCOINUSDT", "LONG", 100, "Primary")
    assert dispatcher.send_raw_message.await_count == 1


async def test_system_alert_honors_cooldown(dispatcher):
    await dispatcher.send_system_alert("SOP-25 NEAR", "x", cooldown_seconds=300)
    await dispatcher.send_system_alert("SOP-25 NEAR", "x", cooldown_seconds=300)
    await dispatcher.send_system_alert("OTRO EVENTO", "y", cooldown_seconds=300)
    assert dispatcher.send_raw_message.await_count == 2


async def test_tp_hit_and_close_not_repeated(dispatcher):
    for _ in range(3):
        await dispatcher.send_tp_hit_alert("BNBUSDT", "PROTEGIDO_TP2", 791.92, 39.37)
        await dispatcher.send_trade_closed_alert("BNBUSDT", "SL", 780.0, -5.0)
    await dispatcher.send_tp_hit_alert("BNBUSDT", "PROTEGIDO_FAST_BE", 799.92, 19.99)
    assert dispatcher.send_raw_message.await_count == 3


async def test_state_survives_restart(dispatcher):
    await dispatcher.send_unauthorized_position_alert("DOGEUSDT", "SHORT", 5, "Primary")
    reborn = td.TelegramDispatcher()
    reborn.enabled = True
    reborn.send_raw_message = AsyncMock(return_value=True)
    await reborn.send_unauthorized_position_alert("DOGEUSDT", "SHORT", 5, "Primary")
    assert reborn.send_raw_message.await_count == 0
