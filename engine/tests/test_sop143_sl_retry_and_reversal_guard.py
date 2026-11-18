import pytest
from unittest.mock import AsyncMock, patch
from engine.execution.bitunix_executor import BitunixExecutor


@pytest.mark.asyncio
async def test_sop143_place_position_tpsl_retries_before_emergency_close():
    executor = BitunixExecutor(dry_run=False, api_key="test", secret_key="test")
    pos = [{"symbol": "NEARUSDT", "side": "SELL", "positionId": "pos_1"}]

    with patch.object(executor, "get_pending_positions", new_callable=AsyncMock, return_value=pos), \
         patch.object(executor, "get_ticker_price", new_callable=AsyncMock, side_effect=[3.50, 3.35]), \
         patch.object(executor, "close_position_market", new_callable=AsyncMock) as mock_close, \
         patch.object(executor, "_request", new_callable=AsyncMock, return_value={"code": 0, "data": {"orderId": "tp_1"}}):

        # SL en 3.40 para SHORT: primer tick 3.50 (lag), segundo tick 3.35 (sano) -> NO debe cerrar
        await executor.place_position_tpsl(symbol="NEARUSDT", position_id="pos_1", sl_price=3.40, tp_price=3.20)
        mock_close.assert_not_awaited()


@pytest.mark.asyncio
async def test_sop143_auto_healing_or_tp_only_never_triggers_emergency_close():
    executor = BitunixExecutor(dry_run=False, api_key="test", secret_key="test")
    with patch.object(executor, "_request", new_callable=AsyncMock, return_value={"code": -1, "msg": "Network glitch"}), \
         patch.object(executor, "close_position_market", new_callable=AsyncMock) as mock_close:

        # 1. Fallo colocando solo TP (sl_price=None) NUNCA debe cerrar la posición a mercado
        await executor.place_position_tpsl(symbol="NEARUSDT", position_id="pos_1", tp_price=3.079)
        mock_close.assert_not_awaited()

        # 2. Fallo en AUTO-HEALING (allow_emergency_close=False) NUNCA debe cerrar la posición a mercado
        await executor.place_position_tpsl(symbol="NEARUSDT", position_id="pos_1", sl_price=3.446, allow_emergency_close=False)
        mock_close.assert_not_awaited()

