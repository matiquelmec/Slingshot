import pytest

from engine.execution.bitunix_executor import BitunixExecutor


@pytest.mark.asyncio
async def test_bitunix_execute_signal_uses_nominal_position_size_for_qty():
    executor = BitunixExecutor(dry_run=True)
    executor.dry_run = False
    executor.api_key = "test-key"
    executor.secret_key = "test-secret"

    calls = []

    async def fake_request(method, path, params=None, json_body=None):
        calls.append((method, path, json_body))
        if path.endswith("/place_order"):
            return {"code": 0, "data": {"orderId": "order-1"}}
        return {"code": 0, "data": {}}

    executor._request = fake_request

    result = await executor.execute_signal(
        {
            "asset": "BTCUSDT",
            "type": "LONG",
            "price": 50000.0,
            "position_size": 1000.0,
            "leverage": 10,
            "stop_loss": 49000.0,
        }
    )

    main_order = next(body for _, path, body in calls if path.endswith("/place_order"))

    assert result["status"] == "success"
    assert main_order["qty"] == "0.02"


@pytest.mark.asyncio
async def test_bitunix_scale_position_uses_nominal_amount_for_qty():
    executor = BitunixExecutor(dry_run=True)
    executor.dry_run = False
    executor.api_key = "test-key"
    executor.secret_key = "test-secret"

    calls = []

    async def fake_request(method, path, params=None, json_body=None):
        calls.append((method, path, json_body))
        if path.endswith("/market/ticker"):
            return {"code": 0, "data": {"lastPrice": 50000.0}}
        if path.endswith("/place_order"):
            return {"code": 0, "data": {"orderId": "scale-1"}}
        return {"code": 0, "data": {}}

    executor._request = fake_request

    success = await executor.scale_position(
        symbol="BTCUSDT",
        side="buy",
        amount_usd=500.0,
        leverage=10,
    )

    scale_order = next(body for _, path, body in calls if path.endswith("/place_order"))

    assert success is True
    assert scale_order["qty"] == "0.01"
