"""
engine/tests/test_bio_connectome_guard.py
=============================================================================
Pruebas Unitarias para el Fast-Path Velocity Sentinel:
1. Activación de escape ante caída violenta para posiciones LONG.
2. Invarianza ante movimientos favorables rápidos.
3. Activación de escape ante subida violenta para posiciones SHORT.
"""

import time
import pytest
from engine.risk.bio_connectome_guard import GiantFiberReflex


def test_giant_fiber_reflex_triggers_on_rapid_adverse_drop_for_long():
    """
    Verifica que el centinela de escape evacúe una posición LONG
    si el precio cae a velocidad anómala (>= 1.5% en menos de 15s).
    """
    gfr = GiantFiberReflex(velocity_threshold_pct=0.015, window_seconds=15.0)
    now = time.time()

    # Entrada en 100.0
    entry_price = 100.0
    gfr.record_tick("SOLUSDT", price=100.0, timestamp=now - 5.0)
    
    # 5 segundos después, caída violenta a 98.0 (-2.0% adverso)
    should_escape, reason = gfr.check_emergency_escape(
        asset="SOLUSDT",
        current_price=98.0,
        position_side="LONG",
        entry_price=entry_price
    )

    assert should_escape is True
    assert "FAST-PATH ESCAPE" in reason
    assert "Caída anómala" in reason


def test_giant_fiber_reflex_ignores_favorable_rapid_moves():
    """
    Verifica que si el precio se mueve rápidamente a favor (subida fuerte para un LONG),
    el escape NO se dispare (no es una amenaza).
    """
    gfr = GiantFiberReflex(velocity_threshold_pct=0.015, window_seconds=15.0)
    now = time.time()

    entry_price = 100.0
    gfr.record_tick("SOLUSDT", price=100.0, timestamp=now - 5.0)

    # Subida rápida a 103.0 (+3% a favor)
    should_escape, reason = gfr.check_emergency_escape(
        asset="SOLUSDT",
        current_price=103.0,
        position_side="LONG",
        entry_price=entry_price
    )

    assert should_escape is False
    assert reason == ""


def test_giant_fiber_reflex_triggers_on_rapid_rise_for_short():
    """
    Verifica que para una posición SHORT, una subida violenta active el escape.
    """
    gfr = GiantFiberReflex(velocity_threshold_pct=0.015, window_seconds=15.0)
    now = time.time()

    entry_price = 100.0
    gfr.record_tick("ETHUSDT", price=100.0, timestamp=now - 5.0)

    # Subida violenta a 102.0 (+2.0% adverso para SHORT)
    should_escape, reason = gfr.check_emergency_escape(
        asset="ETHUSDT",
        current_price=102.0,
        position_side="SHORT",
        entry_price=entry_price
    )

    assert should_escape is True
    assert "Subida anómala" in reason
