"""
engine/tests/test_market_scanner_hft.py
=============================================================================
PRUEBAS UNITARIAS: ESCÁNER DE OPORTUNIDADES CON ENRIQUECIMIENTO HFT & OTE
=============================================================================
Valida:
1. Conexión de fallback seguro del HFT Sidecar.
2. Detección de zonas OTE (Fibonacci 61.8% - 78.6%) y penalización de OTE Watchdog.
3. Enriquecimiento de hipótesis con el Advisor IA en lote.
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from engine.workers.market_scanner import MarketScanner
from engine.core.store import store

@pytest.mark.asyncio
async def test_market_scanner_session_integration():
    """Valida que el escáner obtenga la sesión desde session_manager de forma consistente."""
    scanner = MarketScanner()
    session_data = scanner._calculate_session()
    
    assert "current_session" in session_data
    assert "yosh_window" in session_data
    assert "is_killzone" in session_data

@pytest.mark.asyncio
async def test_market_scanner_ote_watchdog_chasing_detection():
    """Valida que el OTE Watchdog penalice los setups que persiguen el precio en zonas desfavorables."""
    scanner = MarketScanner()
    
    fib_data = {
        "levels": {
            "0.5": 100.0,
            "0.618": 95.0,
            "0.786": 88.0
        }
    }
    
    # Caso 1: Compra (LONG) en precio 105 (Zona Premium > 50% Fibo) -> Chasing = True
    is_chasing, label = scanner._ote_watchdog("LONG", 105.0, fib_data)
    assert is_chasing is True, "Comprar en zona Premium debe ser marcado como Chasing"
    assert "Zona Premium" in label
    
    # Caso 2: Compra (LONG) en precio 94 (Zona Discount < 50% Fibo) -> Chasing = False
    is_chasing_ok, _ = scanner._ote_watchdog("LONG", 94.0, fib_data)
    assert is_chasing_ok is False, "Comprar en zona Discount es válido y no es Chasing"


@pytest.mark.asyncio
async def test_daily_timeframe_aware_gating():
    """
    [SOP-122] Valida que el escáner aplique gating consciente de la temporalidad:
    Las señales en 1D representan estructuras macro y no deben ser vetadas
    por las ventanas intradiarias estrictas (SOP-18 10h/14h o fuera de Killzones).
    """
    scanner = MarketScanner()
    now_utc = datetime(2026, 10, 20, 10, 0, tzinfo=timezone.utc)  # 10:00 UTC es hora tóxica para 15m

    # 1. En 15m a las 10:00 UTC -> debe estar bloqueado por SOP-18
    is_time_15m = scanner.is_trade_allowed_sop18("BTCUSDT", now_utc)
    assert is_time_15m is False, "10:00 UTC debe ser bloqueado para 15m intradía"

    # 2. En _format_opportunity con 1d -> is_time_ok debe ser True
    mock_sig = {
        "asset": "BTCUSDT",
        "signal_type": "LONG",
        "price": 65000.0,
        "stop_loss": 63000.0,
        "confluence": {"score": 80, "asset_health": {"ker": 0.45}}
    }
    opp_1d = scanner._format_opportunity(mock_sig, is_active=False, interval="1d")
    assert opp_1d["is_time_blocked"] is False, "1D debe ser inmune al veto intradiario de killzones"

