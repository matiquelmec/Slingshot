import pytest
from unittest.mock import AsyncMock, patch, MagicMock

@pytest.mark.asyncio
async def test_asset_incubator_imports_cleanly_without_loguru():
    """Valida que asset_incubator se importe sin dependencias faltantes como loguru."""
    from engine.workers.asset_incubator import AssetIncubator, CANONICAL_AUDITED_UNIVERSE
    assert "NEARUSDT" in CANONICAL_AUDITED_UNIVERSE
    assert len(CANONICAL_AUDITED_UNIVERSE) == 13
    incubator = AssetIncubator()
    assert incubator is not None

@pytest.mark.asyncio
async def test_close_position_market_injects_position_id_in_payload():
    """Valida que close_position_market incluya positionId numérico para evitar Parameter error 10002."""
    from engine.execution.bitunix_executor import BitunixExecutor
    executor = BitunixExecutor(dry_run=False)
    executor.api_key = "k"
    executor.secret_key = "s"

    captured_payloads = []
    async def mock_req(method, path, params=None, json_body=None):
        if json_body:
            captured_payloads.append((path, json_body))
        if "/api/v1/futures/position/get_pending_positions" in path:
            return {
                "code": 0,
                "data": [{
                    "symbol": "NEARUSDT",
                    "positionId": "6206257468200691483",
                    "side": "BUY",
                    "qty": "204"
                }]
            }
        if "/api/v1/futures/trade/place_order" in path:
            return {"code": 0, "data": {"orderId": "close_123"}}
        return {"code": 0, "data": {}}

    executor._request = mock_req

    success = await executor.close_position_market("NEARUSDT")
    assert success is True
    assert len(captured_payloads) > 0
    close_payload = next(b for p, b in captured_payloads if b.get("tradeSide") == "CLOSE")
    assert close_payload["symbol"] == "NEARUSDT"
    assert close_payload["side"] == "SELL"
    assert close_payload["positionId"] == "6206257468200691483"
    assert close_payload["orderType"] == "MARKET"

@pytest.mark.asyncio
async def test_place_position_tpsl_preserves_existing_tp():
    """Valida que al actualizar el Stop Loss no se borre el Take Profit existente en Bitunix."""
    from engine.execution.bitunix_executor import BitunixExecutor
    executor = BitunixExecutor(dry_run=False)
    executor.api_key = "k"
    executor.secret_key = "s"

    captured_payloads = []
    async def mock_req(method, path, params=None, json_body=None):
        if json_body:
            captured_payloads.append((path, json_body))
        if "/api/v1/futures/tpsl/get_pending_orders" in path:
            return {
                "code": 0,
                "data": [{
                    "positionId": "6206257468200691483",
                    "slPrice": "4.950",
                    "tpPrice": "5.500",
                    "id": "tpsl_old_1"
                }]
            }
        if "/api/v1/futures/tpsl/position/modify_order" in path:
            return {"code": 0, "data": {"orderId": "tpsl_mod_1"}}
        return {"code": 0, "data": {}}

    executor._request = mock_req

    # Actualizamos sólo sl_price, sin pasar tp_price
    order_id = await executor.place_position_tpsl(
        symbol="NEARUSDT",
        position_id="6206257468200691483",
        sl_price=5.000,
        tp_price=None
    )
    assert order_id == "tpsl_mod_1"
    mod_payload = next(b for p, b in captured_payloads if "/modify_order" in p)
    assert mod_payload["slPrice"] == "5.000"
    assert mod_payload["tpPrice"] == "5.500"  # Preservado de la orden previa
