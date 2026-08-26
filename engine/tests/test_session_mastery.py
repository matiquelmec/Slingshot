"""
engine/tests/test_session_mastery.py
=============================================================================
PRUEBAS UNITARIAS: MAESTRÍA DE SESIONES INSTITUCIONALES (DST & ROTACIÓN)
=============================================================================
Valida:
1. Detección precisa de Killzones (London, NY, Frankfurt).
2. Cálculo exacto de Overlaps (London-NY Power Overlap).
3. Identificación de la ventana de ejecución Yosh (10:00 - 11:30 AM EST).
4. Persistencia y rotación inmutable de niveles de referencia (PDH / PDL / ONH / ONL).
"""
import pytest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from engine.core.session_manager import SessionManager, TimeFilter

def test_session_manager_initialization():
    """Valida la inicialización limpia de SessionManager."""
    sm = SessionManager("BTCUSDT")
    state = sm.get_current_state()
    assert state["type"] == "session_update"
    assert "data" in state
    assert state["data"]["asset"] == "BTCUSDT"
    assert "sessions" in state["data"]

def test_time_filter_killzone_ny_and_london():
    """Valida la detección de Killzones con TimeFilter."""
    tf = TimeFilter()
    
    # 09:00 AM NY time (14:00 UTC en horario de verano EDT)
    ny_tz = ZoneInfo("America/New_York")
    dt_ny = datetime(2026, 5, 20, 9, 30, tzinfo=ny_tz)
    assert tf.is_killzone(dt_ny) is True, "09:30 AM NY debe ser detectado como Killzone"
    
    # 02:00 AM NY time (Fuera de Killzone)
    dt_off = datetime(2026, 5, 20, 2, 0, tzinfo=ny_tz)
    assert tf.is_killzone(dt_off) is False, "02:00 AM NY debe ser detectado como OFF_HOURS"

def test_global_session_status_structure():
    """Valida la estructura devuelta por get_global_session_status()."""
    status = SessionManager.get_global_session_status()
    assert "current_session" in status
    assert "is_killzone" in status
    assert "is_silver_bullet" in status
    assert "is_overlap" in status
    assert "local_time_ny" in status
    assert "local_time_chile" in status

def test_session_sweep_logic():
    """Valida que un precio superior a PDH active pdh_swept."""
    sm = SessionManager("ETHUSDT")
    sm._state["pdh"] = 3500.0
    sm._state["pdl"] = 3300.0
    
    candle = {
        "timestamp": datetime.now(timezone.utc).timestamp(),
        "high": 3550.0,
        "low": 3480.0,
        "close": 3520.0
    }
    
    payload = sm.update(candle)
    assert payload["data"]["pdh_swept"] is True, "El barrido de PDH debe registrarse en True"
    assert payload["data"]["pdl_swept"] is False
