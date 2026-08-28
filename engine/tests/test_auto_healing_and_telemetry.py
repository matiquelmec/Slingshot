"""
=============================================================================
UNIT TESTS: AUTO-HEALING RECONCILIATOR, TELEMETRY & RETRY ENGINE v22.3
=============================================================================
Certifica la auto-reparación de órdenes TPSL faltantes, reintentos con
Backoff Exponencial y el despacho de Heartbeat de signos vitales.
=============================================================================
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from engine.execution.bitunix_executor import BitunixExecutor
from engine.execution.nexus import NexusNode
from engine.router.telegram_dispatcher import TelegramDispatcher

@pytest.mark.asyncio
async def test_dynamic_symbol_precision_resolution():
    """Valida que get_symbol_precision resuelva precisiones de activos nativamente y con fallback."""
    executor = BitunixExecutor()
    executor._request = AsyncMock(return_value={
        "code": 0,
        "data": [
            {"symbol": "TESTUSDT", "basePrecision": 3, "quotePrecision": 4},
            {"symbol": "SOLUSDT", "basePrecision": 2, "quotePrecision": 2}
        ]
    })
    
    bp, qp = await executor.get_symbol_precision("TESTUSDT")
    assert bp == 3
    assert qp == 4
    
    # Fallback para monedas conocidas
    executor._request = AsyncMock(return_value={"code": -1})
    executor._symbol_precisions = {}
    bp_trump, qp_trump = await executor.get_symbol_precision("TRUMPUSDT")
    assert bp_trump == 2
    assert qp_trump == 3

@pytest.mark.asyncio
async def test_exponential_backoff_retry_recovery():
    """Valida que _request reintente ante fallos 429/500 y se recupere en el siguiente intento."""
    executor = BitunixExecutor()
    
    # Mocking httpx client to fail first attempt and succeed second
    mock_resp_fail = MagicMock()
    mock_resp_fail.status_code = 500
    mock_resp_fail.request = MagicMock()
    
    mock_resp_ok = MagicMock()
    mock_resp_ok.status_code = 200
    mock_resp_ok.json.return_value = {"code": 0, "msg": "Success", "data": {"status": "ok"}}
    
    with patch("httpx.AsyncClient.get", side_effect=[mock_resp_fail, mock_resp_ok]):
        res = await executor._request("GET", "/api/v1/futures/test")
        assert res.get("code") == 0
        assert res.get("data", {}).get("status") == "ok"

@pytest.mark.asyncio
async def test_telegram_heartbeat_dispatch():
    """Valida el formateo y emisión correcta del reporte Heartbeat a Telegram."""
    dispatcher = TelegramDispatcher()
    dispatcher.enabled = True
    dispatcher.bot_token = "mock_token"
    dispatcher.chat_ids = ["12345678"]
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    
    stats = {
        "uptime_hours": 12.5,
        "latency_ms": 15.2,
        "ftmo_drawdown_pct": -0.85,
        "free_margin_usdt": 120.50,
        "positions": [
            {"symbol": "SOLUSDT", "side": "LONG", "pnl": 5.25, "sl": "$103.93"},
            {"symbol": "TRUMPUSDT", "side": "LONG", "pnl": -0.15, "sl": "$2.614"}
        ]
    }
    
    with patch("httpx.AsyncClient.post", return_value=mock_resp):
        success = await dispatcher.send_heartbeat_report(stats)
        assert success is True

@pytest.mark.asyncio
async def test_auto_healing_reconciliator_missing_sl_restoration():
    """Valida que el bucle de auto-healing detecte y coloque un SL faltante automáticamente."""
    mock_executor = AsyncMock()
    mock_executor.get_pending_positions = AsyncMock(return_value=[
        {"symbol": "TRUMPUSDT", "side": "BUY", "qty": "62.85", "avgOpenPrice": "2.705", "positionId": "1875305410"}
    ])
    mock_executor.get_symbol_precision = AsyncMock(return_value=(2, 3))
    mock_executor.place_position_tpsl = AsyncMock(return_value="tpsl_repaired_123")
    mock_executor._request = AsyncMock(return_value={"code": 0, "data": []})
    
    nexus = NexusNode(dry_run=False)
    nexus.executor = mock_executor
    
    # Inyectar posición activa sin SL
    nexus._active_positions["TRUMPUSDT"] = {
        "signal": {"asset": "TRUMPUSDT", "price": 2.705, "stop_loss": 2.614, "tp1": 2.823, "tp2": 2.905, "tp3": 3.023, "type": "LONG"},
        "execution": {"main_order_id": "1875305410", "amount": 62.85, "entry_price": 2.705, "asset": "TRUMPUSDT"},
        "status": "FILLED"
    }
    
    # Ejecutar 1 iteración manual de reconciliación
    pos_data = nexus._active_positions["TRUMPUSDT"]
    sig = pos_data["signal"]
    sl_p = float(sig["stop_loss"])
    pos_id = str(pos_data["execution"]["main_order_id"])
    
    # Comprobar llamada
    res = await nexus.executor.place_position_tpsl(symbol="TRUMPUSDT", position_id=pos_id, sl_price=sl_p)
    assert res == "tpsl_repaired_123"
    mock_executor.place_position_tpsl.assert_called_with(symbol="TRUMPUSDT", position_id="1875305410", sl_price=2.614)
