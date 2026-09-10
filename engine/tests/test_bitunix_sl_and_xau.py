"""
engine/tests/test_bitunix_sl_and_xau.py
=============================================================================
Pruebas Unitarias para:
1. Blindaje contra posiciones desprotegidas en BitunixExecutor (SOP-45 Anti-Naked).
2. Manejo de precio perforado (breached SL) con salida de emergencia a mercado.
3. Precisión canónica y reglas de XAUUSDT vs descarte de PAXG.
=============================================================================
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

import sys
sys.path.append(r'C:\Users\Matías Riquelme\Desktop\Proyectos documentados\Slingshot_Trading')

from engine.execution.bitunix_executor import BitunixExecutor
from engine.workers.market_scanner import MarketScanner
from engine.api.config import settings


@pytest.fixture
def dry_executor():
    """Ejecutor en modo Dry Run."""
    return BitunixExecutor(
        api_key="test_key",
        secret_key="test_secret",
        dry_run=True,
        account_label="TestAccount"
    )


@pytest.mark.asyncio
async def test_xauusdt_precision_and_paxg_discard(dry_executor):
    """Verifica que XAUUSDT tenga precisión (3, 2) y que el scanner no incluya PAXG."""
    # 1. Precisión de XAUUSDT
    base_p, quote_p = await dry_executor.get_symbol_precision("XAUUSDT")
    assert base_p == 3
    assert quote_p == 2

    # 2. MarketScanner listas oficiales
    scanner = MarketScanner()
    assert "XAUUSDT" in scanner.core_swing_1h_assets
    assert "XAUUSDT" in scanner.daily_assets
    assert "PAXGUSDT" not in scanner.core_swing_1h_assets
    assert "PAXGUSDT" not in scanner.daily_assets
    assert "PAXGUSDT" in settings.EXCLUDED_DYNAMIC_ASSETS


@pytest.mark.asyncio
async def test_sl_breached_triggers_emergency_market_close():
    """
    Escenario idéntico al fallo real de SUIUSDT:
    - Posición LONG abierta.
    - Target SL = 0.7932.
    - Precio de mercado actual cayó a 0.7929 (target_sl >= current_price).
    - El ejecutor DEBE detectar la perforación y ejecutar cierre a mercado en vez de fallar.
    """
    executor = BitunixExecutor(
        api_key="mock_key",
        secret_key="mock_secret",
        dry_run=False,
        account_label="LiveTest"
    )

    # Mock de métodos internos
    executor.get_pending_positions = AsyncMock(return_value=[
        {"symbol": "SUIUSDT", "positionId": "5664526378562032289", "side": "BUY", "qty": "100"}
    ])
    executor.get_ticker_price = AsyncMock(return_value=0.7929)
    executor.close_position_market = AsyncMock(return_value=True)
    executor._request = AsyncMock()

    # Intentar colocar SL en 0.7932 (superior al precio de mercado 0.7929)
    res = await executor.place_position_tpsl(
        symbol="SUIUSDT",
        position_id="5664526378562032289",
        sl_price=0.7932
    )

    # No debe devolver orden válida y debe haber llamado a close_position_market
    assert res is None
    executor.close_position_market.assert_called_once_with(
        symbol="SUIUSDT",
        position_id="5664526378562032289"
    )


@pytest.mark.asyncio
async def test_sl_short_breached_triggers_emergency_market_close():
    """
    Escenario SHORT perforado:
    - Posición SHORT abierta.
    - Target SL = 1.0500.
    - Precio de mercado subió a 1.0550 (target_sl <= current_price).
    - El ejecutor DEBE disparar cierre a mercado de emergencia.
    """
    executor = BitunixExecutor(
        api_key="mock_key",
        secret_key="mock_secret",
        dry_run=False,
        account_label="LiveTestShort"
    )

    executor.get_pending_positions = AsyncMock(return_value=[
        {"symbol": "XRPUSDT", "positionId": "999888777", "side": "SELL", "qty": "500"}
    ])
    executor.get_ticker_price = AsyncMock(return_value=1.0550)
    executor.close_position_market = AsyncMock(return_value=True)

    res = await executor.place_position_tpsl(
        symbol="XRPUSDT",
        position_id="999888777",
        sl_price=1.0500
    )

    assert res is None
    executor.close_position_market.assert_called_once_with(
        symbol="XRPUSDT",
        position_id="999888777"
    )


@pytest.mark.asyncio
async def test_valid_sl_update_with_invariance():
    """
    Escenario normal válido:
    - Posición LONG en SOLUSDT.
    - Precio actual = 145.00.
    - SL existente = 140.00.
    - Nuevo SL = 142.00 (mayor al existente y menor al precio de mercado).
    - Debe cancelar el anterior y colocar el nuevo con éxito.
    """
    executor = BitunixExecutor(
        api_key="mock_key",
        secret_key="mock_secret",
        dry_run=False,
        account_label="LiveTestValid"
    )

    executor.get_pending_positions = AsyncMock(return_value=[
        {"symbol": "SOLUSDT", "positionId": "pos_sol_123", "side": "BUY", "qty": "10"}
    ])
    executor.get_ticker_price = AsyncMock(return_value=145.00)
    
    # Mock de _request para simular get_pending_orders, cancel_order y place_order
    async def mock_request(method, endpoint, params=None, json_body=None):
        if "get_pending_orders" in endpoint:
            return {"code": 0, "data": [{"id": "old_sl_1", "slPrice": "140.00"}]}
        elif "cancel_order" in endpoint:
            return {"code": 0, "msg": "Success"}
        elif "place_order" in endpoint:
            return {"code": 0, "data": {"orderId": "new_sl_2"}}
        return {"code": 0}

    executor._request = AsyncMock(side_effect=mock_request)

    res = await executor.place_position_tpsl(
        symbol="SOLUSDT",
        position_id="pos_sol_123",
        sl_price=142.00
    )

    assert res == "new_sl_2"


@pytest.mark.asyncio
async def test_rescue_mechanism_when_placement_fails():
    """
    Si la colocación del nuevo SL falla persistentemente,
    el ejecutor intenta un SL de emergencia antes de cerrar a mercado.
    """
    executor = BitunixExecutor(
        api_key="mock_key",
        secret_key="mock_secret",
        dry_run=False,
        account_label="LiveTestRescue"
    )

    executor.get_pending_positions = AsyncMock(return_value=[
        {"symbol": "BTCUSDT", "positionId": "btc_pos_1", "side": "BUY", "qty": "0.1"}
    ])
    executor.get_ticker_price = AsyncMock(return_value=60000.0)

    # Fallar todos los intentos de place_order para forzar cierre a mercado de seguridad
    async def mock_request(method, endpoint, params=None, json_body=None):
        if "get_pending_orders" in endpoint:
            return {"code": 0, "data": []}
        elif "place_order" in endpoint:
            return {"code": 10001, "msg": "Exchange overloaded"}
        return {"code": 0}

    executor._request = AsyncMock(side_effect=mock_request)
    executor.close_position_market = AsyncMock(return_value=True)

    res = await executor.place_position_tpsl(
        symbol="BTCUSDT",
        position_id="btc_pos_1",
        sl_price=59500.0
    )

    # Debe haber ejecutado close_position_market como salvaguarda final
    assert res is None
    executor.close_position_market.assert_called_once_with(
        symbol="BTCUSDT",
        position_id="btc_pos_1"
    )
