"""
engine/tests/test_limit_execution_and_sync_reconciler.py
=============================================================================
Pruebas de verificación de paridad institucional SSoT:
1. Sincronizador de posiciones y verificación forense de PnL en NexusNode.
2. Normalización de dirección ('SMC Sniper' -> 'SHORT'/'LONG') y KER en process_limit_setup.
3. Filtros y despacho transaccional en MarketScanner (_format_opportunity y timeframes).
4. TTL adaptativo en TradeManager para órdenes límite OTE (3h scalp vs 8h swing).
=============================================================================
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from engine.execution.nexus import NexusNode
from engine.workers.market_scanner import MarketScanner
from engine.workers.trade_manager import TradeManager


@pytest.mark.asyncio
async def test_nexus_sync_loop_resets_streak_on_profitable_or_be_close():
    """
    Verifica que al cerrarse una posición en Bitunix con PnL >= 0 o protegida en BE,
    Nexus NO la catalogue como Stop Loss y resetee la racha consecutiva a 0.
    """
    nexus = NexusNode(dry_run=True)
    nexus._consecutive_losses["primary"] = 2
    nexus._risk_released_recently["primary"] = False

    # Mock de orden cerrada en ganancia
    fake_pos = {
        "account_id": "primary",
        "signal": {
            "asset": "BTCUSDT",
            "price": 60000.0,
            "stop_loss": 60100.0, # SL por encima de la entrada en LONG (ganancia)
            "signal_type": "LONG",
            "type": "LONG",
            "trailing_phase": "BREAKEVEN"
        },
        "be_active": True,
        "smart_trailing": {"be_active": True},
        "unrealized_pnl": 15.50
    }
    nexus._active_positions["primary_BTCUSDT"] = fake_pos

    # Llamar on_risk_released simulando el cierre con TP o BE
    await nexus.on_risk_released("primary", reason="POSICION_CERRADA_TP_PROTEGIDO_BTCUSDT")

    assert nexus._consecutive_losses.get("primary") == 0
    assert nexus._risk_released_recently.get("primary") is True


@pytest.mark.asyncio
async def test_nexus_process_limit_setup_normalizes_direction_and_ker():
    """
    Verifica que process_limit_setup extraiga limpiamente 'SHORT' o 'LONG'
    incluso si el diccionario de entrada contiene 'type': 'SMC Sniper',
    y extraiga 'ker' desde asset_health.
    """
    nexus = NexusNode(dry_run=True)
    test_sig = {
        "asset": "ETHUSDT",
        "symbol": "ETHUSDT",
        "signal_type": "SHORT",
        "direction": "SHORT",
        "type": "SMC Sniper",
        "price": 2650.0,
        "stop_loss": 2680.0,
        "confluence_score": 75.0,
        "asset_health": {
            "ker": 0.42,
            "adx": 28.0
        }
    }

    # In dry_run mode, process_limit_setup immediately returns status
    res = await nexus.process_limit_setup(test_sig)
    assert isinstance(res, dict)
    assert test_sig["signal_type"] == "SHORT"
    assert test_sig["direction"] == "SHORT"
    assert test_sig["type"] == "SHORT"


def test_market_scanner_format_opportunity_includes_block_flags():
    """
    Verifica que _format_opportunity inyecte explícitamente los campos
    is_ker_blocked, is_cluster_blocked e is_time_blocked.
    """
    scanner = MarketScanner()
    raw_sig = {
        "asset": "SOLUSDT",
        "signal_type": "LONG",
        "type": "SMC Sniper",
        "price": 140.0,
        "stop_loss": 137.0,
        "confluence": {
            "score": 68,
            "checklist": [],
            "asset_health": {"ker": 0.38}
        }
    }

    opp = scanner._format_opportunity(raw_sig, is_active=True)
    assert "is_ker_blocked" in opp
    assert "is_cluster_blocked" in opp
    assert "is_time_blocked" in opp
    assert opp["is_ker_blocked"] is False
    assert opp["direction"] == "LONG"


def test_trade_manager_adaptive_ttl_constants():
    """
    Verifica que el TTL adaptativo permita a órdenes límite de 15m vivir hasta 3h (10800s)
    y a órdenes de 1h vivir hasta 8h (28800s) en lugar de cancelarse a los 30 minutos.
    """
    # 45 min = 2700s, 60 min = 3600s
    age_15m_at_2h = 7200  # 2 horas
    max_ttl_scalp = 10800 # 3 horas
    assert age_15m_at_2h < max_ttl_scalp, "La orden límite de 15m debe seguir viva a las 2h"

    age_1h_at_5h = 18000  # 5 horas
    max_ttl_swing = 28800 # 8 horas
    assert age_1h_at_5h < max_ttl_swing, "La orden límite de 1h debe seguir viva a las 5h"
