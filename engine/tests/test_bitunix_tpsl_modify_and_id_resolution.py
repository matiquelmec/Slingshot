"""
engine/tests/test_bitunix_tpsl_modify_and_id_resolution.py
=============================================================================
PRUEBAS UNITARIAS: RESOLUCIÓN DE POSITION_ID, PROTOCOLO DUAL TPSL Y PRESERVACIÓN 1R
=============================================================================
Valida:
1. Auto-resolución de position_id cuando es None, vacío o no coincide en modify_position_tpsl.
2. Protocolo Dual TPSL: intento de modify_order con fallback a cancelación + place_order.
3. Blindaje del Rescue Mechanism: no cerrar a mercado si ya existía orden de protección previa.
4. Preservación del riesgo base 1R en TradeManager ante avance del mitigador (-0.5R).
5. Normalización de global_pos_id (position_id / id / main_order_id) en _apply_sl_update.
=============================================================================
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from engine.execution.bitunix_executor import BitunixExecutor
from engine.workers.trade_manager import TradeManager
from engine.core.store import store


@pytest.fixture
def mock_executor():
    ex = BitunixExecutor(
        api_key="mock_key",
        secret_key="mock_secret",
        dry_run=False,
        account_label="PrimaryTest"
    )
    return ex


@pytest.mark.asyncio
async def test_modify_position_tpsl_auto_resolves_none_position_id(mock_executor):
    """
    Si position_id es None o vacío, modify_position_tpsl debe consultar get_pending_positions
    y resolver el positionId real del exchange para el símbolo dado.
    """
    mock_positions = [
        {
            "symbol": "SOXLUSDT",
            "positionId": "987654321",
            "side": "BUY",
            "qty": "1.0",
            "entryPrice": "119.75",
            "markPrice": "125.00",
            "slPrice": "117.59"
        }
    ]

    with patch.object(mock_executor, "get_pending_positions", new_callable=AsyncMock) as mock_get_pos:
        mock_get_pos.return_value = mock_positions
        with patch.object(mock_executor, "place_position_tpsl", new_callable=AsyncMock) as mock_place:
            mock_place.return_value = "order_tpsl_111"

            success = await mock_executor.modify_position_tpsl(
                symbol="SOXLUSDT",
                position_id=None,
                sl_price=124.43
            )

            assert success is True
            mock_get_pos.assert_called_once()
            # Se debe haber llamado a place_position_tpsl con el position_id resuelto ("987654321")
            mock_place.assert_called_once_with(
                symbol="SOXLUSDT",
                position_id="987654321",
                sl_price=124.43,
                tp_price=None
            )


@pytest.mark.asyncio
async def test_dual_protocol_modify_order_success(mock_executor):
    """
    Si ya existe una orden TPSL previa (eo_id), place_position_tpsl debe intentar primero
    POST /api/v1/futures/tpsl/position/modify_order. Si responde éxito, retorna el orderId.
    """
    # 1. Simular que existe una orden TPSL previa
    mock_tpsl_orders = {
        "code": 0,
        "data": [
            {
                "orderId": "prev_tpsl_555",
                "symbol": "SOXLUSDT",
                "slPrice": "117.59",
                "positionId": "pos_soxl_1"
            }
        ]
    }

    mock_modify_response = {
        "code": 0,
        "msg": "Success",
        "data": {"orderId": "prev_tpsl_555"}
    }

    async def fake_request(method, endpoint, **kwargs):
        if endpoint == "/api/v1/futures/tpsl/get_pending_orders":
            return mock_tpsl_orders
        elif endpoint == "/api/v1/futures/tpsl/position/modify_order":
            return mock_modify_response
        return {"code": 0, "data": {}}

    with patch.object(mock_executor, "_request", side_effect=fake_request) as mock_req:
        with patch.object(mock_executor, "get_ticker_price", new_callable=AsyncMock, return_value=126.0):
            with patch.object(mock_executor, "get_symbol_rules", new_callable=AsyncMock, return_value={"price_precision": 2, "qty_precision": 2}):
                with patch.object(mock_executor, "get_pending_positions", new_callable=AsyncMock, return_value=[
                    {"symbol": "SOXLUSDT", "positionId": "pos_soxl_1", "side": "BUY"}
                ]):
                    order_id = await mock_executor.place_position_tpsl(
                        symbol="SOXLUSDT",
                        position_id="pos_soxl_1",
                        sl_price=124.43
                    )

                    assert order_id == "prev_tpsl_555"


@pytest.mark.asyncio
async def test_dual_protocol_fallback_cancel_then_place(mock_executor):
    """
    Si modify_order falla o es rechazado (code != 0), place_position_tpsl debe cancelar
    la orden previa preventivamente y luego llamar a place_order exitosamente.
    """
    mock_tpsl_orders = {
        "code": 0,
        "data": [
            {
                "orderId": "prev_tpsl_999",
                "symbol": "SOXLUSDT",
                "slPrice": "117.59",
                "positionId": "pos_soxl_1"
            }
        ]
    }

    calls = []

    async def fake_request(method, endpoint, **kwargs):
        calls.append((method, endpoint, kwargs))
        if endpoint == "/api/v1/futures/tpsl/get_pending_orders":
            return mock_tpsl_orders
        elif endpoint == "/api/v1/futures/tpsl/position/modify_order":
            # Simular rechazo de Bitunix al endpoint modify_order
            return {"code": 10001, "msg": "Endpoint not supported for this order type"}
        elif endpoint == "/api/v1/futures/trade/cancel_order":
            return {"code": 0, "msg": "Success"}
        elif endpoint == "/api/v1/futures/tpsl/position/place_order":
            return {"code": 0, "msg": "Success", "data": {"orderId": "new_tpsl_1000"}}
        return {"code": 0, "data": {}}

    with patch.object(mock_executor, "_request", side_effect=fake_request):
        with patch.object(mock_executor, "get_ticker_price", new_callable=AsyncMock, return_value=126.0):
            with patch.object(mock_executor, "get_symbol_rules", new_callable=AsyncMock, return_value={"price_precision": 2, "qty_precision": 2}):
                with patch.object(mock_executor, "get_pending_positions", new_callable=AsyncMock, return_value=[
                    {"symbol": "SOXLUSDT", "positionId": "pos_soxl_1", "side": "BUY"}
                ]):
                    order_id = await mock_executor.place_position_tpsl(
                        symbol="SOXLUSDT",
                        position_id="pos_soxl_1",
                        sl_price=124.43
                    )

                    assert order_id == "new_tpsl_1000"
                    endpoints_called = [c[1] for c in calls]
                    assert "/api/v1/futures/tpsl/position/modify_order" in endpoints_called
                    assert "/api/v1/futures/trade/cancel_order" in endpoints_called
                    assert "/api/v1/futures/tpsl/position/place_order" in endpoints_called


@pytest.mark.asyncio
async def test_rescue_mechanism_does_not_market_close_if_previous_protection_exists(mock_executor):
    """
    Si fallan todas las llamadas de actualización pero la posición YA contaba con una orden
    previa activa (eo_id), NO debe ejecutarse close_position_market bajo ninguna circunstancia.
    """
    mock_tpsl_orders = {
        "code": 0,
        "data": [
            {
                "orderId": "prev_tpsl_shield",
                "symbol": "SOXLUSDT",
                "slPrice": "117.59",
                "positionId": "pos_soxl_1"
            }
        ]
    }

    async def fake_failing_request(method, endpoint, **kwargs):
        if endpoint == "/api/v1/futures/tpsl/get_pending_orders":
            return mock_tpsl_orders
        # Todos los intentos de colocar / modificar fallan por timeout o error 500
        return {"code": 50000, "msg": "Exchange Gateway Error"}

    with patch.object(mock_executor, "_request", side_effect=fake_failing_request):
        with patch.object(mock_executor, "get_ticker_price", new_callable=AsyncMock, return_value=126.0):
            with patch.object(mock_executor, "get_symbol_rules", new_callable=AsyncMock, return_value={"price_precision": 2, "qty_precision": 2}):
                with patch.object(mock_executor, "get_pending_positions", new_callable=AsyncMock, return_value=[
                    {"symbol": "SOXLUSDT", "positionId": "pos_soxl_1", "side": "BUY"}
                ]):
                    with patch.object(mock_executor, "close_position_market", new_callable=AsyncMock) as mock_close:
                        order_id = await mock_executor.place_position_tpsl(
                            symbol="SOXLUSDT",
                            position_id="pos_soxl_1",
                            sl_price=124.43
                        )

                        # place_position_tpsl retorna None porque no pudo actualizar
                        assert order_id is None
                        # El mecanismo de rescate NO debe haber cerrado la posición porque ya tenía protección activa
                        mock_close.assert_not_called()


@pytest.mark.asyncio
async def test_trade_manager_preserves_initial_1r_risk_cache():
    """
    Valida que TradeManager preserve la distancia de riesgo 1R original en su cache
    incluso después de que el SL haya sido elevado al mitigador (-0.5R).
    """
    tm = TradeManager()
    acc_id = "primary"
    sym = "SOXLUSDT"
    pos_id = "pos_999"

    entry_price = 119.75
    # Supongamos que el SL inicial era 115.43 -> 1R = 4.32
    initial_sl = 115.43
    cached_key = f"{acc_id}_{sym}_{pos_id}"

    # Simular que se guarda la señal en el store
    await store.save_signal({
        "asset": sym,
        "symbol": sym,
        "entry_price": entry_price,
        "stop_loss": initial_sl,
        "initial_stop_loss": initial_sl,
        "direction": "LONG",
        "position_id": pos_id
    })

    # 1. Primera consulta: posición con SL inicial
    mock_pos_1 = [{
        "symbol": sym,
        "positionId": pos_id,
        "side": "BUY",
        "avgOpenPrice": str(entry_price),
        "lastPrice": "122.50",
        "slPrice": str(initial_sl)
    }]

    mock_executor = MagicMock()
    mock_executor.account_label = "TestAcc"
    mock_executor.get_pending_positions = AsyncMock(return_value=mock_pos_1)
    mock_executor.get_ticker_price = AsyncMock(return_value=122.50)
    mock_executor._request = AsyncMock(return_value={"code": 0, "data": []})
    mock_executor.modify_position_tpsl = AsyncMock(return_value=True)

    with patch("engine.execution.account_manager.AccountManager.get_all_executors", return_value={acc_id: mock_executor}):
        results1 = await tm.sync_live_bitunix_positions()
        # Verificar que se registró en cache el 1R correcto (4.32)
        assert cached_key in tm._initial_risk_cache
        assert abs(tm._initial_risk_cache[cached_key] - 4.32) < 0.01

        # 2. Segunda consulta: el SL en el exchange ahora es 117.59 (mitigador -0.5R)
        # y el precio actual subió a 124.50 (+1.10R sobre el 1R original de 4.32)
        mock_pos_2 = [{
            "symbol": sym,
            "positionId": pos_id,
            "side": "BUY",
            "avgOpenPrice": str(entry_price),
            "lastPrice": "124.50",
            "slPrice": "117.59"
        }]
        mock_executor.get_pending_positions = AsyncMock(return_value=mock_pos_2)
        mock_executor.get_ticker_price = AsyncMock(return_value=124.50)

        results2 = await tm.sync_live_bitunix_positions()
        # El cache debe mantenerse en 4.32 (no reducirse a 119.75 - 117.59 = 2.16)
        assert abs(tm._initial_risk_cache[cached_key] - 4.32) < 0.01
        # Con precio 124.50 y 1R=4.32, (124.50 - 119.75) / 4.32 = 1.10R
        # Por tanto, r_profit debe ser ~1.10R, no un valor inflado ni distorsionado
        assert len(results2) > 0
        assert results2[0]["r_profit"] >= 1.0


@pytest.mark.asyncio
async def test_apply_sl_update_normalizes_signal_id_keys():
    """
    Valida que _apply_sl_update resuelva correctamente el ID de la posición tanto si
    viene en position_id, id o main_order_id.
    """
    tm = TradeManager()

    signal_with_id_only = {
        "asset": "SOXLUSDT",
        "id": "soxl_pos_canonical_1",
        "price": 119.75,
        "stop_loss": 117.59,
        "direction": "LONG",
        "trailing_history": []
    }

    mock_executor = MagicMock()
    mock_executor.account_label = "Primary"
    mock_executor.modify_position_tpsl = AsyncMock(return_value=True)

    with patch("engine.execution.account_manager.AccountManager.get_all_executors", return_value={"primary": mock_executor}):
        await tm._apply_sl_update(signal_with_id_only, 124.43, "TRAILING", "TRAILING_TEST")

        mock_executor.modify_position_tpsl.assert_called_once_with(
            symbol="SOXLUSDT",
            position_id="soxl_pos_canonical_1",
            sl_price=124.43
        )
