"""
engine/tests/test_bio_connectome_guard.py
=============================================================================
Pruebas Unitarias para el Módulo Bio-Inspirado (Drosophila Connectome Principles):
1. Giant Fiber Reflex (Escape ultrarrápido ante anomalías de precio).
2. Lateral Feedforward Inhibition (Silenciamiento de altcoins subordinadas ante shock en nodo ancla).
3. Período Refractario (Vencimiento de la inhibición biológica).
"""

import time
import pytest
from engine.risk.bio_connectome_guard import GiantFiberReflex, LateralInhibitionEngine


def test_giant_fiber_reflex_triggers_on_rapid_adverse_drop_for_long():
    """
    Verifica que el reflejo de escape (Giant Fiber) evacúe una posición LONG
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
    assert "GIANT FIBER REFLEX" in reason
    assert "Caída violenta" in reason


def test_giant_fiber_reflex_ignores_favorable_rapid_moves():
    """
    Verifica que si el precio se mueve rápidamente a favor (subida fuerte para un LONG),
    el reflejo de escape NO se dispare (no es una amenaza).
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
    assert "Subida violenta" in reason


def test_lateral_inhibition_silences_subordinates_on_anchor_shock():
    """
    Verifica que un shock bajista en BTCUSDT inhiba compras en altcoins del cluster (SOL, NEAR, AVAX, etc.).
    """
    engine = LateralInhibitionEngine(refractory_period_seconds=600.0)
    engine.clear_inhibition()

    # Inicialmente, SOLUSDT puede operar LONG sin inhibición
    inhibited_pre, _ = engine.is_inhibited("SOLUSDT", "LONG")
    assert inhibited_pre is False

    # Disparar shock bajista en el nodo ancla (BTCUSDT)
    affected = engine.register_anchor_shock(
        anchor_asset="BTCUSDT",
        shock_direction="BEARISH_DUMP",
        reason="Dump institucional súbito"
    )

    assert "SOLUSDT" in affected
    assert "ETHUSDT" in affected
    assert "NEARUSDT" in affected

    # Ahora una señal de compra (LONG) en SOL debe estar inhibida
    inhibited_post, msg = engine.is_inhibited("SOLUSDT", "LONG")
    assert inhibited_post is True
    assert "INHIBICIÓN LATERAL" in msg

    # Sin embargo, una señal SHORT en SOL NO debe estar inhibida (alineada con el shock)
    inhibited_short, _ = engine.is_inhibited("SOLUSDT", "SHORT")
    assert inhibited_short is False


def test_lateral_inhibition_expires_after_refractory_period():
    """
    Verifica que tras el período refractario, la inhibición desaparezca.
    """
    # Período refractario de prueba ultracorto (0.1 segundos)
    engine = LateralInhibitionEngine(refractory_period_seconds=0.1)
    engine.clear_inhibition()

    engine.register_anchor_shock("BTCUSDT", "BEARISH")
    assert engine.is_inhibited("SOLUSDT", "LONG")[0] is True

    # Esperar que expire el período refractario
    time.sleep(0.15)

    is_inh, _ = engine.is_inhibited("SOLUSDT", "LONG")
    assert is_inh is False
