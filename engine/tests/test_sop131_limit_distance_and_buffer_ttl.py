"""
engine/tests/test_sop131_limit_distance_and_buffer_ttl.py
=============================================================================
Pruebas unitarias y de integración para SOP-131:
1. NexusNode.validate_limit_distance (distancia máxima Bitunix L1, cross-book).
2. Expiración TTL (45 min) y persistencia en SQLite del buffer de alta confluencia.
3. Bloqueo pre-flight BLOCKED_STALE_DISTANCE en process_limit_setup con reloj aislado.
=============================================================================
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from engine.execution.nexus import NexusNode


def test_validate_limit_distance_rejects_stale_1h_gold_and_15m_scalp():
    # XAUUSDT 1h swing: max 1.5%
    ok_1h, reason_1h, dist_1h = NexusNode.validate_limit_distance(
        entry_price=2550.0,
        live_price=2630.0,
        side="LONG",
        interval="1h",
    )
    assert ok_1h is False
    assert "1.50%" in reason_1h or "lejana" in reason_1h.lower()
    assert dist_1h > 0.015

    # 15m scalp: max 1.2%
    ok_15m, reason_15m, dist_15m = NexusNode.validate_limit_distance(
        entry_price=2600.0,
        live_price=2645.0,
        side="LONG",
        interval="15m",
    )
    assert ok_15m is False
    assert dist_15m > 0.012


def test_validate_limit_distance_rejects_cross_book_and_accepts_valid_pullback():
    # LONG limit por encima del precio live -> cruzaría el libro a mercado
    ok_long_cross, reason_long, _ = NexusNode.validate_limit_distance(
        entry_price=2640.0,
        live_price=2630.0,
        side="LONG",
        interval="1h",
    )
    assert ok_long_cross is False
    assert "LONG" in reason_long

    # SHORT limit por debajo del precio live -> cruzaría el libro a mercado
    ok_short_cross, reason_short, _ = NexusNode.validate_limit_distance(
        entry_price=2620.0,
        live_price=2630.0,
        side="SHORT",
        interval="1h",
    )
    assert ok_short_cross is False
    assert "SHORT" in reason_short

    # Pullback válido dentro del 1.5% en 1h (0.76%)
    ok_valid, reason_valid, dist_valid = NexusNode.validate_limit_distance(
        entry_price=2610.0,
        live_price=2630.0,
        side="LONG",
        interval="1h",
    )
    assert ok_valid is True
    assert reason_valid == "DISTANCE_OK"
    assert dist_valid < 0.015


@pytest.mark.asyncio
async def test_buffer_ttl_discards_expired_signals_and_persists_pop():
    nexus = NexusNode(dry_run=True)
    nexus._high_confluence_buffer.clear()

    stale_ts = time.time() - 3600  # 60 min atrás (> 45 min TTL)
    fresh_ts = time.time() - 120   # 2 min atrás (válida)

    nexus._high_confluence_buffer["primary"] = [
        {"asset": "XAUUSDT", "signal_type": "LONG", "price": 2550.0, "confluence_score": 88.0, "queued_at": stale_ts},
        {"asset": "BTCUSDT", "signal_type": "LONG", "price": 90000.0, "confluence_score": 82.0, "queued_at": fresh_ts},
    ]

    with (
        patch.object(nexus, "_persist_buffer_to_disk") as mock_persist,
        patch.object(nexus, "_persist_streak_state"),
        patch.object(nexus, "process_limit_setup", new_callable=AsyncMock, return_value={"status": "SIMULATED"}) as mock_process,
    ):
        await nexus.on_risk_released("primary", reason="TP_HIT_TEST")
        await __import__("asyncio").sleep(0)

    # La señal expirada (XAUUSDT) debe haberse descartado y la fresca (BTCUSDT) procesado
    assert mock_process.await_count == 1
    dispatched_sig = mock_process.call_args.args[0]
    assert dispatched_sig["asset"] == "BTCUSDT"
    assert nexus._high_confluence_buffer["primary"] == []
    assert mock_persist.call_count >= 1


@pytest.mark.asyncio
async def test_process_limit_setup_blocks_stale_xauusdt_distance():
    nexus = NexusNode(dry_run=False)
    mock_executor = MagicMock()
    mock_executor.dry_run = False
    mock_executor.get_ticker_price = AsyncMock(return_value=2650.0)
    mock_executor.get_pending_positions = AsyncMock(return_value=[])
    mock_executor.get_pending_orders = AsyncMock(return_value=[])
    mock_executor.get_available_margin_usdt = AsyncMock(return_value=1000.0)
    mock_executor.get_net_available_margin_usdt = AsyncMock(return_value=1000.0)
    mock_executor.get_account_balance = AsyncMock(return_value=1000.0)
    mock_executor.get_symbol_precision = AsyncMock(return_value=(3, 2))
    mock_executor.place_limit_signal = AsyncMock()
    mock_account = MagicMock(
        account_id="primary",
        label="Primary",
        is_primary=True,
        risk_pct=0.025,
        risk_multiplier=1.0,
        max_risk_pct=1.0,
        max_notional_mult=5.0,
    )
    nexus.account_manager.get_all_accounts = MagicMock(return_value=[mock_account])
    nexus.account_manager.get_enabled_accounts = MagicMock(return_value=[mock_account])
    nexus.account_manager.get_executor = MagicMock(return_value=mock_executor)

    stale_gold_signal = {
        "asset": "XAUUSDT",
        "symbol": "XAUUSDT",
        "signal_type": "LONG",
        "direction": "LONG",
        "type": "SMC Sniper",
        "interval": "1h",
        "price": 2590.0,       # 2.26% por debajo de 2650.0 -> excede 1.5%
        "stop_loss": 2565.0,
        "confluence_score": 85.0,
        "asset_health": {"ker": 0.45, "adx": 30.0},
    }

    with patch("engine.workers.market_scanner.is_trade_allowed_sop18", return_value=(True, "TEST_BYPASS")):
        res = await nexus.process_limit_setup(stale_gold_signal)

    assert res.get("status") == "BLOCKED_STALE_DISTANCE"
    mock_executor.place_limit_signal.assert_not_awaited()
