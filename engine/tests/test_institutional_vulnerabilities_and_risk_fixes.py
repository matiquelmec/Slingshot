"""
engine/tests/test_institutional_vulnerabilities_and_risk_fixes.py
=============================================================================
SUITE DE CERTIFICACIÓN DE VULNERABILIDADES Y BLINDAJE DE RIESGO FINANCIERO
1. Fast Breakeven Fuga de Riesgo: No libera cupo si Bitunix rechaza el SL.
2. Stop Loss Atómico con Reintentos de Emergencia y Alarma Crítica en Fallo.
3. Purga Aislada de Órdenes Límite: Cero contaminación entre cuentas.
4. Precisión Dinámica de Lotes por Símbolo (Zero Parameter Error en Bitunix).
=============================================================================
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from engine.execution.bitunix_executor import BitunixExecutor
from engine.execution.nexus import NexusNode
from engine.workers.trade_manager import TradeManager


@pytest.mark.asyncio
async def test_fast_be_does_not_release_risk_on_bitunix_failure():
    """
    VULNERABILIDAD #1:
    Valida que si Bitunix rechaza la actualización de Stop Loss al entrar en Fast BE (+1.0R),
    el sistema NO invoque on_risk_released, evitando sobre-exposición de la cuenta.
    """
    tm = TradeManager()
    
    mock_executor = MagicMock(spec=BitunixExecutor)
    mock_executor.account_label = "TestAccount"
    # Simulamos fallo en la API de Bitunix (ej. timeout o error de red)
    mock_executor.modify_position_tpsl = AsyncMock(return_value=False)
    mock_executor.get_pending_positions = AsyncMock(return_value=[{
        "positionId": "123456",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "avgOpenPrice": "60000.0",
        "lastPrice": "61500.0",
        "slPrice": "59000.0",
        "margin": "100.0"
    }])
    mock_executor._request = AsyncMock(return_value={"code": 0, "data": []})

    mock_mgr = MagicMock()
    mock_mgr.get_all_executors.return_value = {"primary": mock_executor}

    with patch("engine.execution.account_manager.AccountManager", return_value=mock_mgr), \
         patch("engine.execution.nexus.nexus.get_unprotected_risk_count", return_value=1), \
         patch("engine.execution.nexus.nexus.on_risk_released", new_callable=AsyncMock) as mock_release:

        await tm.sync_live_bitunix_positions()
        await asyncio.sleep(0.01)
        
        # Debe haber intentado modificar el SL
        assert mock_executor.modify_position_tpsl.called
        # Como modify_position_tpsl retornó False, on_risk_released NO debe haberse llamado
        assert not mock_release.called, "Fuga de riesgo detectada: on_risk_released se llamó a pesar del fallo en Bitunix"


@pytest.mark.asyncio
async def test_fast_be_releases_risk_only_on_bitunix_success():
    """Valida que si Bitunix confirma la actualización de SL, el cupo de riesgo SÍ se libere."""
    tm = TradeManager()
    
    mock_executor = MagicMock(spec=BitunixExecutor)
    mock_executor.account_label = "TestAccount"
    mock_executor.modify_position_tpsl = AsyncMock(return_value=True)
    mock_executor.get_pending_positions = AsyncMock(return_value=[{
        "positionId": "123456",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "avgOpenPrice": "60000.0",
        "lastPrice": "61500.0",
        "slPrice": "59000.0",
        "margin": "100.0"
    }])
    mock_executor._request = AsyncMock(return_value={"code": 0, "data": []})

    mock_mgr = MagicMock()
    mock_mgr.get_all_executors.return_value = {"primary": mock_executor}

    with patch("engine.execution.account_manager.AccountManager", return_value=mock_mgr), \
         patch("engine.execution.nexus.nexus.get_unprotected_risk_count", return_value=1), \
         patch("engine.execution.nexus.nexus.on_risk_released", new_callable=AsyncMock) as mock_release:

        await tm.sync_live_bitunix_positions()
        await asyncio.sleep(0.01)
        assert mock_executor.modify_position_tpsl.called
        assert mock_release.called, "on_risk_released debió ser invocado tras confirmación exitosa de Bitunix"


@pytest.mark.asyncio
async def test_atomic_tpsl_emergency_fallback_and_alert():
    """
    VULNERABILIDAD #2:
    Valida que place_position_tpsl reintente ante fallos transitorios y, si se canceló un SL previo
    y todos los reintentos fallan, emita una alarma crítica de emergencia.
    """
    ex = BitunixExecutor(api_key="test_key", secret_key="test_sec", account_label="test_acc", dry_run=False)
    
    fake_orders = {
        "code": 0,
        "data": [{
            "orderId": "old_sl_999",
            "symbol": "ETHUSDT",
            "slPrice": "2400.0"
        }]
    }

    async def fake_request(method, path, params=None, json_body=None):
        if "trading_pairs" in path:
            return {"code": 0, "data": [{"symbol": "ETHUSDT", "basePrecision": 3, "quotePrecision": 2}]}
        if "get_pending_orders" in path:
            return fake_orders
        if "cancel_order" in path:
            return {"code": 0, "msg": "Cancelled"}
        if "place_order" in path:
            return {"code": 500, "msg": "Bitunix 502 Bad Gateway"}
        return {"code": 0, "data": {}}

    with patch.object(ex, "_request", side_effect=fake_request), \
         patch("engine.router.telegram_dispatcher.telegram_dispatcher.send_system_alert", new_callable=AsyncMock) as mock_alert, \
         patch("asyncio.sleep", new_callable=AsyncMock):

        order_id = await ex.place_position_tpsl("ETHUSDT", "pos_555", sl_price=2450.0)
        assert order_id is None
        # Debe haber disparado alerta crítica a Telegram porque el SL previo se canceló y los reintentos fallaron
        assert mock_alert.called
        call_kwargs = mock_alert.call_args.kwargs
        assert call_kwargs.get("severity") == "CRITICAL"
        assert "ETHUSDT" in call_kwargs.get("title")


@pytest.mark.asyncio
async def test_limit_order_purge_isolated_to_saturated_account():
    """
    VULNERABILIDAD #3:
    Valida que purge_all_pending_limit_orders(account_id=acc_id) purgue ÚNICAMENTE
    las órdenes de la cuenta indicada sin tocar las órdenes de otras cuentas sanas.
    """
    nexus = NexusNode(dry_run=True)
    
    mock_ex_primary = MagicMock(spec=BitunixExecutor)
    mock_ex_primary.account_label = "primary"
    mock_ex_primary.get_pending_orders = AsyncMock(return_value=[
        {"symbol": "SOLUSDT", "orderId": "ord_p1", "tradeSide": "OPEN", "orderType": "LIMIT"}
    ])
    mock_ex_primary.cancel_limit_order = AsyncMock(return_value=True)

    mock_ex_c2 = MagicMock(spec=BitunixExecutor)
    mock_ex_c2.account_label = "cliente_2"
    mock_ex_c2.get_pending_orders = AsyncMock(return_value=[
        {"symbol": "XAUUSDT", "orderId": "ord_c2_1", "tradeSide": "OPEN", "orderType": "LIMIT"}
    ])
    mock_ex_c2.cancel_limit_order = AsyncMock(return_value=True)

    mock_mgr = MagicMock()
    mock_mgr.get_all_executors.return_value = {
        "primary": mock_ex_primary,
        "cliente_2": mock_ex_c2
    }
    nexus.account_manager = mock_mgr

    # Purgamos SOLO la cuenta "primary" por saturación
    await nexus.purge_all_pending_limit_orders(reason="MAX_4_RISK_SLOTS_REACHED", account_id="primary")

    # primary DEBE haber cancelado su orden
    mock_ex_primary.cancel_limit_order.assert_awaited_once_with("SOLUSDT", "ord_p1")
    # cliente_2 NO debe haber sufrido cancelaciones
    assert not mock_ex_c2.cancel_limit_order.called, "Contaminación detectada: cliente_2 fue purgado al saturarse primary"


@pytest.mark.asyncio
async def test_lot_precision_dynamic_formatting_respects_specs():
    """
    VULNERABILIDAD #4:
    Valida que update_stop_loss y scale_position formateen la cantidad según
    qty_precision del activo (ej. FETUSDT = 0 decimales, BTCUSDT = 4 decimales).
    """
    ex = BitunixExecutor(api_key="test_key", secret_key="test_sec", account_label="test_acc", dry_run=False)
    
    captured_payloads = []
    async def fake_request(method, path, params=None, json_body=None):
        if "trading_pairs" in path:
            return {"code": 0, "data": [
                {"symbol": "FETUSDT", "basePrecision": 0, "quotePrecision": 4},
                {"symbol": "BTCUSDT", "basePrecision": 4, "quotePrecision": 1}
            ]}
        if "place_order" in path:
            captured_payloads.append(json_body)
            return {"code": 0, "data": {"orderId": "new_order_123"}}
        if "ticker" in path:
            return {"code": 0, "data": {"lastPrice": "2.50"}}
        return {"code": 0, "data": {}}

    with patch.object(ex, "_request", side_effect=fake_request):
        # 1. Test update_stop_loss para FETUSDT (cantidad 123.4567 -> debe formatearse a entero "123")
        await ex.update_stop_loss(symbol="FETUSDT", old_order_id="", new_stop_price=2.10, amount=123.4567, side="BUY")
        assert len(captured_payloads) == 1
        assert captured_payloads[0]["qty"] == "123", f"FETUSDT debe tener 0 decimales, actual: {captured_payloads[0]['qty']}"

        # 2. Test scale_position para FETUSDT con $50 USD a $2.50 (50 / 2.5 = 20 -> entero "20")
        await ex.scale_position(symbol="FETUSDT", side="BUY", amount_usd=50.0, leverage=5)
        assert len(captured_payloads) == 2
        assert captured_payloads[1]["qty"] == "20"
