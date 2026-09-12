import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from engine.execution.bitunix_executor import BitunixExecutor

@pytest.mark.asyncio
async def test_bitunix_telemetry_summary_structure():
    """Valida la estructura formal y esquema de get_account_telemetry_summary."""
    executor = BitunixExecutor(api_key="test", secret_key="test", account_label="Test Primary", dry_run=True)
    
    mock_acc = {
        "code": 0,
        "data": {
            "available": "500.0",
            "marginBalance": "600.0",
            "positionMargin": "100.0",
            "unrealizedProfit": "15.50"
        }
    }
    mock_positions = [
        {
            "symbol": "AVAXUSDT",
            "positionId": "12345",
            "side": "BUY",
            "qty": "95",
            "entryPrice": "7.962",
            "markPrice": "8.100",
            "leverage": 18,
            "isolatedMargin": "42.0"
        }
    ]
    mock_orders = [
        {
            "orderId": "999",
            "symbol": "AVAXUSDT",
            "side": "SELL",
            "tradeSide": "CLOSE",
            "orderType": "LIMIT",
            "price": "8.253",
            "qty": "57",
            "reduceOnly": True
        }
    ]
    mock_tpsl = {
        "code": 0,
        "data": [
            {
                "id": "888",
                "positionId": "12345",
                "slPrice": "7.683",
                "triggerPrice": "7.683"
            }
        ]
    }

    with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req, \
         patch.object(executor, "get_pending_positions", new_callable=AsyncMock) as mock_get_pos, \
         patch.object(executor, "get_pending_orders", new_callable=AsyncMock) as mock_get_orders:
        
        async def mock_req_side_effect(method, path, **kwargs):
            if "/futures/account" in path:
                return mock_acc
            if "/tpsl/get_pending_orders" in path:
                return mock_tpsl
            return {"code": 0, "data": {}}

        mock_req.side_effect = mock_req_side_effect
        mock_get_pos.return_value = mock_positions
        mock_get_orders.return_value = mock_orders

        telemetry = await executor.get_account_telemetry_summary()

        assert telemetry["account_label"] == "Test Primary"
        assert telemetry["connected"] is True
        assert telemetry["equity"] == 600.0
        assert telemetry["available_balance"] == 500.0
        assert telemetry["positions_count"] == 1
        
        # Validación de enriquecimiento de posición
        pos = telemetry["positions"][0]
        assert pos["symbol"] == "AVAXUSDT"
        assert pos["side"] == "LONG"
        assert pos["qty"] == 95.0
        assert pos["active_sl"]["is_protected"] is True
        assert pos["active_sl"]["price"] == 7.683
        assert len(pos["take_profits"]) == 1
        assert pos["take_profits"][0]["price"] == 8.253

        # Validación de configuración de riesgo canónico al 2.50% (SOP-41)
        risk = telemetry["risk_config"]
        assert risk["risk_pct"] == 0.025
        assert risk["risk_pct_display"] == "2.50%"
        assert risk["risk_usd_per_trade"] == 15.0  # 600 * 0.025 = 15.0 USDT

@pytest.mark.asyncio
async def test_bitunix_25pct_risk_exact_calculation():
    """Certifica que el cálculo de riesgo en dólares corresponda al 2.50% estricto del balance."""
    executor = BitunixExecutor(api_key="test", secret_key="test", dry_run=True)
    
    mock_acc = {
        "code": 0,
        "data": {
            "available": "648.83",
            "marginBalance": "648.83",
            "positionMargin": "0.0",
            "unrealizedProfit": "0.0"
        }
    }
    with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req, \
         patch.object(executor, "get_pending_positions", new_callable=AsyncMock) as mock_get_pos, \
         patch.object(executor, "get_pending_orders", new_callable=AsyncMock) as mock_get_orders:
        
        mock_req.return_value = mock_acc
        mock_get_pos.return_value = []
        mock_get_orders.return_value = []

        res = await executor.get_account_telemetry_summary()
        # 648.83 * 0.025 = 16.22075 -> redondeado a 16.22 USDT
        assert res["risk_config"]["risk_usd_per_trade"] == 16.22

@pytest.mark.asyncio
async def test_bitunix_real_api_position_payload():
    """Certifica que el payload real de Bitunix (avgOpenPrice, margin, unrealizedPNL, isolationUnrealizedPNL) se parsee fielmente."""
    executor = BitunixExecutor(api_key="test", secret_key="test", dry_run=True)
    mock_acc = {
        "code": 0,
        "data": {
            "marginCoin": "USDT",
            "available": "746.38",
            "margin": "42.17",
            "isolationUnrealizedPNL": "-4.73",
            "crossUnrealizedPNL": "0"
        }
    }
    mock_positions = [
        {
            "positionId": "1138116320852577976",
            "symbol": "BNBUSDT",
            "qty": "1.14",
            "side": "BUY",
            "leverage": 20,
            "margin": "42.17",
            "unrealizedPNL": "-4.73",
            "avgOpenPrice": "730.99"
        }
    ]
    with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req, \
         patch.object(executor, "get_pending_positions", new_callable=AsyncMock) as mock_get_pos, \
         patch.object(executor, "get_pending_orders", new_callable=AsyncMock) as mock_get_orders, \
         patch.object(executor, "get_ticker_price", new_callable=AsyncMock) as mock_ticker:

        mock_req.return_value = mock_acc
        mock_get_pos.return_value = mock_positions
        mock_get_orders.return_value = []
        mock_ticker.return_value = 726.84

        res = await executor.get_account_telemetry_summary()
        pos = res["positions"][0]
        assert pos["symbol"] == "BNBUSDT"
        assert pos["entry_price"] == 730.99
        assert pos["mark_price"] == 726.84
        assert pos["isolated_margin"] == 42.17
        assert pos["side"] == "LONG"
        # pos_pnl = (726.84 - 730.99) * 1.14 = -4.15 * 1.14 = -4.73
        assert pos["unrealized_pnl"] == -4.73
        assert pos["unrealized_pnl_pct"] < 0
        assert res["total_floating_pnl"] == -4.73

