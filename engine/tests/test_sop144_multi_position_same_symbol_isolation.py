import pytest
from unittest.mock import AsyncMock, patch
from engine.workers.trade_manager import TradeManager
from engine.execution.bitunix_executor import BitunixExecutor


@pytest.mark.asyncio
async def test_sop144_trade_manager_isolates_two_positions_same_symbol():
    """
    Verifica que TradeManager no mezcle el Stop Loss ni el cálculo de 1R entre
    dos posiciones simultáneas de la misma moneda (Isolated-Multi) con distinto positionId.
    """
    tm = TradeManager()
    positions = [
        {"symbol": "XRPUSDT", "side": "BUY", "avgOpenPrice": "0.9569", "lastPrice": "0.9621", "positionId": "101"},
        {"symbol": "XRPUSDT", "side": "BUY", "avgOpenPrice": "0.9635", "lastPrice": "0.9621", "positionId": "202"},
    ]

    async def mock_req(method, path, params=None, json_body=None):
        if "/api/v1/futures/tpsl/get_pending_orders" in path:
            return {
                "code": 0,
                "data": [
                    {"positionId": "202", "slPrice": "0.9462", "id": "tpsl_202"},
                ],
            }
        return {"code": 0, "data": []}

    with patch("engine.execution.bitunix_executor.BitunixExecutor.get_pending_positions", new_callable=AsyncMock, return_value=positions), \
         patch("engine.execution.bitunix_executor.BitunixExecutor._request", side_effect=mock_req), \
         patch("engine.execution.bitunix_executor.BitunixExecutor.modify_position_tpsl", new_callable=AsyncMock, return_value=True):

        results = await tm.sync_live_bitunix_positions()
        primary_res = [r for r in results if r.get("account_id") == "primary"]
        assert len(primary_res) == 2
        res_101 = next(r for r in primary_res if abs(r["entry_price"] - 0.9569) < 1e-6)
        res_202 = next(r for r in primary_res if abs(r["entry_price"] - 0.9635) < 1e-6)

        # Posición 101 NO debe heredar el SL 0.9462 de la posición 202
        assert res_101["current_sl"] == 0.0
        assert res_202["current_sl"] == 0.9462


@pytest.mark.asyncio
async def test_sop144_telemetry_filters_tps_and_sl_by_position_id():
    """
    Verifica que get_account_telemetry asigne a cada tarjeta de posición
    únicamente el SL y las órdenes límite TP correspondientes a su positionId.
    """
    executor = BitunixExecutor(dry_run=False, api_key="test", secret_key="test")
    raw_positions = [
        {"symbol": "TIAUSDT", "side": "BUY", "qty": "1788", "avgOpenPrice": "0.3432", "markPrice": "0.3464", "leverage": "10", "positionId": "301"},
        {"symbol": "TIAUSDT", "side": "BUY", "qty": "380", "avgOpenPrice": "0.3430", "markPrice": "0.3464", "leverage": "10", "positionId": "302"},
    ]
    raw_orders = [
        {"symbol": "TIAUSDT", "orderId": "o1", "tradeSide": "CLOSE", "price": "0.3600", "qty": "190", "positionId": "302"},
        {"symbol": "TIAUSDT", "orderId": "o2", "tradeSide": "CLOSE", "price": "0.3700", "qty": "894", "positionId": "301"},
    ]

    async def mock_req(method, path, params=None, json_body=None):
        if "/api/v1/futures/tpsl/get_pending_orders" in path:
            return {"code": 0, "data": [{"positionId": "302", "slPrice": "0.3347", "id": "sl_302"}]}
        return {"code": 0, "data": []}

    with patch.object(executor, "get_balance", new_callable=AsyncMock, return_value={"equity": 1000.0, "available": 500.0, "balance": 1000.0, "used_margin": 100.0}), \
         patch.object(executor, "get_pending_positions", new_callable=AsyncMock, return_value=raw_positions), \
         patch.object(executor, "get_pending_orders", new_callable=AsyncMock, return_value=raw_orders), \
         patch.object(executor, "_request", side_effect=mock_req):

        tel = await executor.get_account_telemetry_summary()
        p301 = next(p for p in tel["positions"] if p["position_id"] == "301")
        p302 = next(p for p in tel["positions"] if p["position_id"] == "302")

        assert p301["active_sl"]["price"] is None
        assert len(p301["take_profits"]) == 1 and p301["take_profits"][0]["order_id"] == "o2"

        assert p302["active_sl"]["price"] == 0.3347
        assert len(p302["take_profits"]) == 1 and p302["take_profits"][0]["order_id"] == "o1"
