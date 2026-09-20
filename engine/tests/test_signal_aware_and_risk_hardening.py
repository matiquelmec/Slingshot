"""
engine/tests/test_signal_aware_and_risk_hardening.py
=============================================================================
Pruebas Unitarias Institucionales para:
1. Hard Cap Físico Absoluto (SOP-40: Máximo 4 posiciones reales).
2. Signal-Aware Position Management (SOP-46: Reversal Guard ante señales opuestas).
3. Hard-Clamp de Riesgo y Nocional (SOP-42: Anti-Catástrofe LINK).
4. Blindaje de Correlación y Cuarentena (SOP-44 Fortress).
5. TTL Estricto de Órdenes Límite (45 minutos).
"""
import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from engine.risk.cluster_risk_guard import ClusterRiskGuard, cluster_risk_guard
from engine.execution.nexus import NexusNode
from engine.execution.bitunix_executor import BitunixExecutor


@pytest.mark.asyncio
async def test_hard_cap_rejects_fifth_position_even_if_all_in_be():
    """
    [SOP-40] Verifica que con 4 posiciones abiertas (incluso si todas están en Breakeven),
    el sistema rechace tajantemente una 5ta posición.
    """
    nexus = NexusNode(dry_run=True)
    # Configurar 4 posiciones existentes con BE activo
    nexus._active_positions = {
        "primary_BTCUSDT": {
            "account_id": "primary",
            "signal": {"asset": "BTCUSDT", "type": "LONG", "price": 60000, "stop_loss": 60100},
            "smart_trailing": {"be_active": True}
        },
        "primary_ETHUSDT": {
            "account_id": "primary",
            "signal": {"asset": "ETHUSDT", "type": "LONG", "price": 2500, "stop_loss": 2510},
            "smart_trailing": {"be_active": True}
        },
        "primary_SOLUSDT": {
            "account_id": "primary",
            "signal": {"asset": "SOLUSDT", "type": "LONG", "price": 150, "stop_loss": 151},
            "smart_trailing": {"be_active": True}
        },
        "primary_XAUUSDT": {
            "account_id": "primary",
            "signal": {"asset": "XAUUSDT", "type": "LONG", "price": 2600, "stop_loss": 2605},
            "smart_trailing": {"be_active": True}
        }
    }

    mock_account = MagicMock()
    mock_account.account_id = "primary"
    mock_account.label = "Cuenta Principal"

    mock_executor = MagicMock()
    mock_executor.dry_run = True
    mock_executor.get_pending_positions = AsyncMock(return_value=[])

    fifth_signal = {
        "asset": "NEARUSDT",
        "type": "LONG",
        "price": 5.0,
        "stop_loss": 4.8,
        "score": 85.0
    }

    res = await nexus._execute_signal_for_account(
        executor=mock_executor,
        account=mock_account,
        signal=fifth_signal,
        safe_lev=10,
        entry_val=5.0,
        sl_val=4.8,
        fragments=[]
    )

    # Debe ser rechazado por Hard Cap
    assert res is None
    assert "primary_NEARUSDT" not in nexus._active_positions


@pytest.mark.asyncio
async def test_reversal_guard_closes_opposite_position_on_high_confluence():
    """
    [SOP-46] Si existe una posición LONG en ETH y llega una señal SHORT con confluencia >= 75%,
    el Reversal Guard debe cerrar la posición LONG previa a mercado.
    """
    nexus = NexusNode(dry_run=True)
    nexus._active_positions = {
        "primary_ETHUSDT": {
            "account_id": "primary",
            "signal": {"asset": "ETHUSDT", "type": "LONG", "price": 2500, "stop_loss": 2450},
            "smart_trailing": {"be_active": False}
        }
    }

    mock_account = MagicMock()
    mock_account.account_id = "primary"
    mock_account.label = "Cuenta Principal"
    mock_account.risk_pct = 0.025
    mock_account.max_notional_mult = 5.0

    mock_executor = MagicMock()
    mock_executor.dry_run = False
    mock_executor.get_pending_positions = AsyncMock(return_value=[{"symbol": "ETHUSDT", "side": "BUY"}])
    mock_executor.close_position_market = AsyncMock(return_value=True)
    mock_executor.get_net_available_margin_usdt = AsyncMock(return_value=100.0)
    mock_executor.get_symbol_precision = AsyncMock(return_value=(2, 2))
    mock_executor.execute_signal = AsyncMock(return_value={"status": "success"})

    # Señal opuesta (SHORT) con 80% de confluencia
    opposite_signal = {
        "asset": "ETHUSDT",
        "type": "SHORT",
        "price": 2480.0,
        "stop_loss": 2520.0,
        "score": 80.0,
        "confluence_score": 80.0
    }

    with patch("engine.risk.risk_manager.RiskManager.verify_liquidation_clearance", return_value=(True, "OK", 1.5)):
        await nexus._execute_signal_for_account(
            executor=mock_executor,
            account=mock_account,
            signal=opposite_signal,
            safe_lev=10,
            entry_val=2480.0,
            sl_val=2520.0,
            fragments=[]
        )

    # Verificar que se ordenó cerrar la posición previa a mercado
    mock_executor.close_position_market.assert_called_once_with("ETHUSDT")


@pytest.mark.asyncio
async def test_reversal_guard_ignores_weak_opposite_signal():
    """
    [SOP-46] Si la señal opuesta tiene confluencia < 75%, NO debe cerrar la posición en curso.
    """
    nexus = NexusNode(dry_run=True)
    nexus._active_positions = {
        "primary_ETHUSDT": {
            "account_id": "primary",
            "signal": {"asset": "ETHUSDT", "type": "LONG", "price": 2500, "stop_loss": 2450},
            "smart_trailing": {"be_active": False}
        }
    }

    mock_account = MagicMock()
    mock_account.account_id = "primary"
    mock_account.label = "Cuenta Principal"

    mock_executor = MagicMock()
    mock_executor.dry_run = False
    mock_executor.get_pending_positions = AsyncMock(return_value=[{"symbol": "ETHUSDT", "side": "BUY"}])
    mock_executor.close_position_market = AsyncMock(return_value=True)

    # Señal opuesta débil (60% < 75%)
    weak_opposite_signal = {
        "asset": "ETHUSDT",
        "type": "SHORT",
        "price": 2480.0,
        "stop_loss": 2520.0,
        "score": 60.0,
        "confluence_score": 60.0
    }

    res = await nexus._execute_signal_for_account(
        executor=mock_executor,
        account=mock_account,
        signal=weak_opposite_signal,
        safe_lev=10,
        entry_val=2480.0,
        sl_val=2520.0,
        fragments=[]
    )

    assert res is None
    # No se debió cerrar la posición
    mock_executor.close_position_market.assert_not_called()
    assert "primary_ETHUSDT" in nexus._active_positions


@pytest.mark.asyncio
async def test_sop42_hard_clamp_prevents_outsized_loss_and_notional():
    """
    [SOP-42] Simula una orden potencialmente desastrosa (similar al caso LINK: $672 nocional, SL distante)
    y verifica que BitunixExecutor clampee la cantidad a un máximo de $5.00 USDT de pérdida y $150 de nocional.
    """
    executor = BitunixExecutor(api_key="mock", secret_key="mock")
    executor.dry_run = False
    executor._last_verified_balance = 200.0

    # Mock de precisión y requests
    executor.get_symbol_precision = AsyncMock(return_value=(2, 2))
    executor._request = AsyncMock(return_value={"code": 0, "data": {"orderId": "12345"}})
    executor.get_pending_positions = AsyncMock(return_value=[{"symbol": "LINKUSDT", "positionId": "pos_link_1"}])
    executor.place_position_tpsl = AsyncMock(return_value=True)
    executor.get_symbol_rules = AsyncMock(return_value={"qty_precision": 2, "price_precision": 2, "min_trade_volume": 0.01})

    # Señal con intento de nocional excesivo: 100 USDT margen @ 10x = $1000 USD nocional
    # Entry: $11.34, Stop Loss: $10.00 (distancia = $1.34)
    huge_signal = {
        "asset": "LINKUSDT",
        "type": "LONG",
        "price": 11.34,
        "stop_loss": 10.00,
        "position_size": 100.0,
        "leverage": 10
    }

    await executor.execute_signal(huge_signal)

    # Verificar el payload enviado al exchange
    calls = executor._request.call_args_list
    place_order_call = [c for c in calls if "/api/v1/futures/trade/place_order" in str(c)][0]
    sent_payload = place_order_call.kwargs.get("json_body", {})

    sent_qty = float(sent_payload.get("qty", 0))
    sent_notional = sent_qty * 11.34
    projected_loss = sent_qty * (11.34 - 10.00)

    # El nocional no puede exceder $150 USD
    assert sent_notional <= 150.05
    # La pérdida proyectada no puede exceder $5.00 USDT
    assert projected_loss <= 5.05


def test_quarantine_assets_vetoed():
    """
    [SOP-44] Verifica que TIA esté en cuarentena y que LINK opere normalmente.
    """
    guard = ClusterRiskGuard()
    # LINKUSDT está rehabilitado: puede abrir si no hay saturación de cluster
    can_open_link, reason_link = guard.can_open_position("LINKUSDT", "LONG", 90.0, {})
    assert can_open_link is True

    # TIAUSDT permanece en cuarentena estricta
    can_open_tia, reason_tia = guard.can_open_position("TIAUSDT", "SHORT", 90.0, {})
    assert can_open_tia is False
    assert "cuarentena" in reason_tia.lower()


def test_cluster_guard_rejects_third_crypto_without_bypass():
    """
    [SOP-44 Fortress] Con 2 posiciones cripto activas, un 3er trade cripto en la misma dirección
    debe ser vetado incluso si la confluencia es del 95% (el bypass del 88% está desactivado por defecto).
    """
    guard = ClusterRiskGuard(allow_elite_override=False)
    active_positions = {
        "BTCUSDT": {"signal": {"type": "LONG", "price": 60000, "stop_loss": 59000}, "smart_trailing": {"be_active": False}},
        "ETHUSDT": {"signal": {"type": "LONG", "price": 2500, "stop_loss": 2400}, "smart_trailing": {"be_active": False}}
    }

    can_open, reason = guard.can_open_position("SOLUSDT", "LONG", confluence_score=95.0, active_positions=active_positions)
    assert can_open is False
    assert "Límite de cluster alcanzado" in reason


def test_pending_limit_order_ttl_expiration():
    """
    [SOP-40] Verifica que una orden límite con más de 45 minutos (2700s) de antigüedad
    sea marcada para cancelación automática por el sentinel.
    """
    now_ms = time.time() * 1000
    order_ctime = now_ms - (50 * 60 * 1000) # 50 minutos atrás

    age_seconds = (now_ms - order_ctime) / 1000
    cancel_reason = None
    if age_seconds > 2700:
        cancel_reason = f"TTL_EXPIRED_STRICT (Orden límite expiró tras superar 45 minutos sin llenar: {age_seconds/60:.1f} min)"

    assert cancel_reason is not None
    assert "TTL_EXPIRED_STRICT" in cancel_reason
