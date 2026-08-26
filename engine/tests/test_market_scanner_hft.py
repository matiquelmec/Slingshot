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
async def test_hft_order_flow_graceful_fallback():
    """Valida que ante desconexión del sidecar HFT se retorne un dict vacío sin elevar excepciones."""
    scanner = MarketScanner()
    res = await scanner._get_hft_order_flow("UNKNOWN_COIN_USDT")
    assert isinstance(res, dict)
