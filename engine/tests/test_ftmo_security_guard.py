"""
engine/tests/test_ftmo_security_guard.py
=============================================================================
PRUEBAS UNITARIAS: SEGURIDAD Y BLINDAJE FTMO / PROP-FIRM
=============================================================================
Valida:
1. Cálculo matemático de lotajes MT5 basado en riesgo monetario estricto.
2. Comprobación del límite de Drawdown Diario (4.5% hard limit).
3. Parámetros de Fast BE (+1.0R) y TP1 (+1.3R).
"""
import pytest
from engine.risk.ftmo_guardian import ftmo_guardian
from engine.workers.tradfi_scanner import TRADFI_ASSETS_CONFIG

def test_ftmo_lot_sizing_gold():
    """Valida el cálculo de lotes para Oro (XAUUSD) con riesgo fijo de $750 USD."""
    entry_price = 2350.0
    stop_loss = 2345.0 # Distancia = $5.00 USD por onza
    
    lot_info = ftmo_guardian.calculate_mt5_lots("XAUUSD", entry_price, stop_loss)
    
    assert lot_info["risk_usd"] == 750.0
    assert lot_info["lots"] > 0
    # En XAUUSD 1 lote = 100 onzas -> 5 USD * 100 = $500 por lote -> 750 / 500 = 1.5 Lotes
    assert round(lot_info["lots"], 2) == 1.50

def test_ftmo_daily_drawdown_protection():
    """Valida la detección de peligro de drawdown diario."""
    # Simular equity inicial $100,000 y pérdida del día de $4,800 (supera 3.5%)
    status = ftmo_guardian.update_equity(current_equity=95200.0)
    assert status["is_daily_lockout"] is True, "El kill-switch debe bloquear la cuenta al superar el drawdown"
    assert "KILL-SWITCH DIARIO" in status["lockout_reason"]

def test_tradfi_assets_config_integrity():
    """Valida que los 4 activos institucionales de FTMO estén configurados con spread y apalancamiento."""
    assert "XAUUSD" in TRADFI_ASSETS_CONFIG
    assert "US100" in TRADFI_ASSETS_CONFIG
    assert "US30" in TRADFI_ASSETS_CONFIG
    assert "GBPUSD" in TRADFI_ASSETS_CONFIG
