import pytest
from unittest.mock import AsyncMock, patch
from engine.execution.bitunix_executor import BitunixExecutor
from engine.execution.nexus import NexusNode


@pytest.mark.asyncio
async def test_sop145_non_destructive_prevalidation_never_closes_position():
    executor = BitunixExecutor(dry_run=False, api_key="test", secret_key="test")
    pos = [{"symbol": "XAUUSDT", "side": "BUY", "positionId": "8646797904868419107"}]

    with patch.object(executor, "get_pending_positions", new_callable=AsyncMock, return_value=pos), \
         patch.object(executor, "get_ticker_price", new_callable=AsyncMock, return_value=4010.0), \
         patch.object(executor, "close_position_market", new_callable=AsyncMock) as mock_close, \
         patch.object(executor, "_request", new_callable=AsyncMock, return_value={"code": 0, "data": []}):

        res = await executor.place_position_tpsl(
            symbol="XAUUSDT",
            position_id="8646797904868419107",
            sl_price=4027.06,
            allow_emergency_close=False,
        )
        assert res is None
        mock_close.assert_not_awaited()


def test_sop145_is_plan_geometrically_valid_rejects_stale_and_inverted_plans():
    # Plan antiguo con entrada alejada (>2%) o SL invertido (>= entry en LONG)
    assert NexusNode._is_plan_geometrically_valid(4010.0, 4027.06, "LONG", plan_entry=4200.0) is False
    assert NexusNode._is_plan_geometrically_valid(4010.0, 4027.06, "LONG", plan_entry=4012.0) is False
    # Plan coherente
    assert NexusNode._is_plan_geometrically_valid(4010.0, 3960.0, "LONG", plan_entry=4012.0) is True
    assert NexusNode._is_plan_geometrically_valid(4010.0, 4060.0, "SHORT", plan_entry=4008.0) is True
