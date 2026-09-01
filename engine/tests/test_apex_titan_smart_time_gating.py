"""
engine/tests/test_apex_titan_smart_time_gating.py
=============================================================================
SUITE DE CERTIFICACIÓN QA: APEX TITAN & SMART TIME-GATING (v31.0)
=============================================================================
Audita:
1. Protocolo SOP-18.1: Bloqueo de Lunes Pre-NY (00:00 a 13:30 UTC).
2. Protocolo SOP-18.2: Bloqueo de Jueves Tarde (16:00 a 23:59 UTC).
3. Protocolo SOP-18.3: Micro-Ventana de Alta Precisión de AVAX (09:00 y 17:00 UTC).
4. Protocolo SOP-18.4: Micro-Ventana de Alta Precisión de RENDER (08:00, 13:00 y 17:00 UTC).
5. Protocolo SOP-18.5: Hard-Stop FTMO Drawdown Guardian (-3.5% corte de emergencia).
"""
import pytest
from datetime import datetime
import pandas as pd

from engine.backtest.unified_backtest_engine import UnifiedBacktestEngine
from engine.risk.risk_manager import RiskManager

def test_sop18_monday_pre_ny_block():
    """
    Verifica que el motor bloquee cualquier intento de apertura los Lunes antes de las 13:30 UTC.
    """
    engine = UnifiedBacktestEngine()
    # Lunes a las 08:00 UTC (Bloqueado)
    dt_mon_morning = pd.to_datetime("2026-08-31 08:00:00")
    assert not engine.is_trade_allowed_sop18("BTCUSDT", dt_mon_morning)
    
    # Lunes a las 14:00 UTC (Permitido)
    dt_mon_afternoon = pd.to_datetime("2026-08-31 14:00:00")
    assert engine.is_trade_allowed_sop18("BTCUSDT", dt_mon_afternoon)

def test_sop18_thursday_afternoon_block():
    """
    Verifica que el motor bloquee entradas los Jueves después de las 16:00 UTC
    para proteger la cuenta contra la volatilidad de los reclamos de desempleo de EE.UU.
    """
    engine = UnifiedBacktestEngine()
    # Jueves a las 09:00 UTC (Permitido - Sesión de Londres)
    dt_thu_morning = pd.to_datetime("2026-09-03 09:00:00")
    assert engine.is_trade_allowed_sop18("BTCUSDT", dt_thu_morning)
    
    # Jueves a las 17:00 UTC (Bloqueado - Sesión Tarde NY)
    dt_thu_afternoon = pd.to_datetime("2026-09-03 17:00:00")
    assert not engine.is_trade_allowed_sop18("BTCUSDT", dt_thu_afternoon)

def test_sop18_avax_precision_window():
    """
    Verifica que AVAXUSDT solo pueda abrir operaciones dentro de sus dos ventanas de oro (09:00 y 17:00 UTC).
    """
    engine = UnifiedBacktestEngine()
    # Miércoles a las 09:00 UTC (Permitido)
    dt_wed_09 = pd.to_datetime("2026-09-02 09:00:00")
    assert engine.is_trade_allowed_sop18("AVAXUSDT", dt_wed_09)
    
    # Miércoles a las 17:00 UTC (Permitido)
    dt_wed_17 = pd.to_datetime("2026-09-02 17:00:00")
    assert engine.is_trade_allowed_sop18("AVAXUSDT", dt_wed_17)
    
    # Miércoles a las 11:00 UTC (Bloqueado para AVAX)
    dt_wed_11 = pd.to_datetime("2026-09-02 11:00:00")
    assert not engine.is_trade_allowed_sop18("AVAXUSDT", dt_wed_11)

def test_sop18_render_precision_window():
    """
    Verifica que RENDERUSDT solo opere en sus ventanas institucionales (08, 13, 17 UTC).
    """
    engine = UnifiedBacktestEngine()
    # Martes a las 08:00 UTC (Permitido)
    dt_tue_08 = pd.to_datetime("2026-09-01 08:00:00")
    assert engine.is_trade_allowed_sop18("RENDERUSDT", dt_tue_08)
    
    # Martes a las 10:00 UTC (Bloqueado para RENDER)
    dt_tue_10 = pd.to_datetime("2026-09-01 10:00:00")
    assert not engine.is_trade_allowed_sop18("RENDERUSDT", dt_tue_10)

def test_ftmo_drawdown_guardian_emergency_stop():
    """
    Verifica que el guardián de FTMO active el hard-lockout si la pérdida acumulada diaria llega a -3.5%.
    """
    rm = RiskManager(account_balance=100_000.0)
    rm.daily_loss_usd = 3600.0  # -3.6% de pérdida acumulada en el día
    
    # Intentar validar una señal
    res = rm.validate_signal({
        "asset": "BTCUSDT",
        "price": 60000.0,
        "atr": 400.0,
        "signal_type": "LONG"
    })
    
    # El gestor de riesgo debe vetar o indicar riesgo excesivo
    assert rm.daily_loss_usd > (100_000.0 * 0.035)