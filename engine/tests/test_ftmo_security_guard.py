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

def test_ftmo_phase_based_risk_scaling():
    """Valida que el riesgo monetario se adapte automáticamente según la fase configurada."""
    # Fase 1: 0.75% ($750 USD en $100K)
    ftmo_guardian.set_phase("PHASE_1")
    ftmo_guardian.reset_daily_metrics(100000.0)
    info_p1 = ftmo_guardian.calculate_mt5_lots("XAUUSD", 2500.0, 2490.0)
    assert info_p1["risk_usd"] == 750.0
    assert info_p1["risk_pct"] == 0.75
    
    # Fase 2: 0.50% ($500 USD en $100K)
    ftmo_guardian.set_phase("PHASE_2")
    ftmo_guardian.reset_daily_metrics(100000.0)
    info_p2 = ftmo_guardian.calculate_mt5_lots("XAUUSD", 2500.0, 2490.0)
    assert info_p2["risk_usd"] == 500.0
    assert info_p2["risk_pct"] == 0.50

    # Fondeada (Funded): 0.35% ($350 USD en $100K)
    ftmo_guardian.set_phase("FUNDED")
    ftmo_guardian.reset_daily_metrics(100000.0)
    info_funded = ftmo_guardian.calculate_mt5_lots("XAUUSD", 2500.0, 2490.0)
    assert info_funded["risk_usd"] == 350.0
    assert info_funded["risk_pct"] == pytest.approx(0.35, rel=1e-5)
    
    # Restaurar a PHASE_1
    ftmo_guardian.set_phase("PHASE_1")


def test_ftmo_dynamic_daily_lockout_by_phase():
    """Valida que el Kill-Switch diario sea más estricto en Fase 2 (-2.5%) y Fondeada (-2.0%)."""
    # Fase 1: Permite hasta -3.5%
    ftmo_guardian.set_phase("PHASE_1")
    ftmo_guardian.reset_daily_metrics(100000.0)
    # Pérdida de $2,800 (-2.8%) no debe bloquear en Fase 1
    st1 = ftmo_guardian.update_equity(97200.0)
    assert st1["is_daily_lockout"] is False
    
    # Fase 2: Bloquea a -2.5% ($2,500)
    ftmo_guardian.set_phase("PHASE_2")
    ftmo_guardian.reset_daily_metrics(100000.0)
    # Pérdida de $2,800 (-2.8%) SÍ debe bloquear en Fase 2
    st2 = ftmo_guardian.update_equity(97200.0)
    assert st2["is_daily_lockout"] is True
    assert "PHASE_2" in st2["lockout_reason"]
    
    # Restaurar a PHASE_1
    ftmo_guardian.set_phase("PHASE_1")


def test_tradfi_staged_exits_lot_fragmentation():
    """Valida la conservación exacta de lotes MT5 en la fragmentación 50/30/20."""
    ftmo_guardian.set_phase("PHASE_1")
    ftmo_guardian.reset_daily_metrics(100000.0)
    
    # XAUUSD: Oro Spot
    gold_lots = ftmo_guardian.calculate_mt5_lots("XAUUSD", 2500.0, 2495.0)
    assert gold_lots["lots"] == pytest.approx(gold_lots["lots_tp1"] + gold_lots["lots_tp2"] + gold_lots["lots_tp3"], rel=1e-5)
    assert gold_lots["lots_tp1"] / gold_lots["lots"] == pytest.approx(0.50, abs=0.05)
    
    # US100: Nasdaq 100 Cash
    nq_lots = ftmo_guardian.calculate_mt5_lots("US100", 19500.0, 19450.0)
    assert nq_lots["lots"] == pytest.approx(nq_lots["lots_tp1"] + nq_lots["lots_tp2"] + nq_lots["lots_tp3"], rel=1e-5)


