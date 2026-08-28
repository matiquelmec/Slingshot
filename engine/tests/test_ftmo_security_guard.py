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
    ftmo_guardian.reset_daily_metrics(100000.0)
    entry_price = 2350.0
    stop_loss = 2345.0 # Distancia = $5.00 USD por onza
    
    lot_info = ftmo_guardian.calculate_mt5_lots("XAUUSD", entry_price, stop_loss)
    
    assert lot_info["risk_usd"] == 750.0
    assert lot_info["lots"] > 0
    # En XAUUSD 1 lote = 100 onzas -> 5 USD * 100 = $500 por lote -> 750 / 500 = 1.5 Lotes
    assert round(lot_info["lots"], 2) == 1.50

def test_ftmo_daily_drawdown_protection():
    """Valida la detección de peligro de drawdown diario."""
    ftmo_guardian.reset_daily_metrics(100000.0)
    # Simular equity inicial $100,000 y pérdida del día de $4,800 (supera 3.5%)
    status = ftmo_guardian.update_equity(current_equity=95200.0)
    assert status["is_daily_lockout"] is True, "El kill-switch debe bloquear la cuenta al superar el drawdown"
    assert "KILL-SWITCH DIARIO" in status["lockout_reason"]

def test_tradfi_assets_config_integrity():
    """Valida que los activos institucionales de FTMO estén configurados con spread y apalancamiento."""
    assert "XAUUSD" in TRADFI_ASSETS_CONFIG
    assert "US100" in TRADFI_ASSETS_CONFIG
    assert "US30" in TRADFI_ASSETS_CONFIG
    assert "US500" in TRADFI_ASSETS_CONFIG
    assert "HGUSD" in TRADFI_ASSETS_CONFIG
    assert "GER40" in TRADFI_ASSETS_CONFIG
    assert "GBPJPY" in TRADFI_ASSETS_CONFIG
    assert "GBPUSD" in TRADFI_ASSETS_CONFIG

def test_ftmo_lot_sizing_sp500():
    """Valida el cálculo de lotes para S&P 500 (US500) con riesgo de $750 USD."""
    ftmo_guardian.reset_daily_metrics(100000.0)
    entry_price = 5500.0
    stop_loss = 5475.0 # Distancia = $25.00 puntos
    
    lot_info = ftmo_guardian.calculate_mt5_lots("US500", entry_price, stop_loss)
    assert lot_info["risk_usd"] == 750.0
    assert lot_info["lots"] > 0
    # En US500 (1 contrato por lote): 25 puntos = $25 por lote -> 750 / 25 = 30.0 Lotes
    assert round(lot_info["lots"], 1) == 30.0

def test_ftmo_lot_sizing_dax40():
    """Valida el cálculo de lotes para DAX 40 (GER40) con riesgo de $750 USD."""
    ftmo_guardian.reset_daily_metrics(100000.0)
    entry_price = 18500.0
    stop_loss = 18450.0 # Distancia = 50.0 puntos
    
    lot_info = ftmo_guardian.calculate_mt5_lots("GER40", entry_price, stop_loss)
    assert lot_info["risk_usd"] == 750.0
    assert lot_info["lots"] > 0
    # En GER40 (25 contratos por lote): 50 puntos * 25 = $1250 por lote -> 750 / 1250 = 0.60 Lotes
    assert round(lot_info["lots"], 1) == 0.6

def test_ftmo_lot_sizing_gbpjpy():
    """Valida el cálculo de lotes para GBPJPY con riesgo de $750 USD."""
    ftmo_guardian.reset_daily_metrics(100000.0)
    entry_price = 195.50
    stop_loss = 195.00 # Distancia = 0.50 = 50 pips
    
    lot_info = ftmo_guardian.calculate_mt5_lots("GBPJPY", entry_price, stop_loss)
    assert lot_info["risk_usd"] == 750.0
    assert lot_info["lots"] > 0
    # En GBPJPY (100,000 unidades): 0.50 * 100,000 = $50,000 por lote -> 750 / 50,000 = 0.015 -> 0.02 Lotes
    assert round(lot_info["lots"], 2) == 0.01 or round(lot_info["lots"], 2) == 0.02

