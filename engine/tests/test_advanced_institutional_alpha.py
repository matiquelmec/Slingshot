"""
=============================================================================
SLINGSHOT v46.5 — ADVANCED INSTITUTIONAL ALPHA QA SUITE (SOP-46 A SOP-49)
=============================================================================
Pruebas cuantitativas de las innovaciones de nivel institucional:
1. SOP-46: Modulacion Ciclica Semanal de Liquidez (Weekly Alpha Cycle).
2. SOP-47: Asignacion de Conviccion Cuantitativa 'Trinidad del Alfa' (BNB, SOL, FET).
3. SOP-48: Runner Elastico Dinamico con Kaufman Efficiency Ratio (KER) y Ratchet Lock.
4. SOP-49: Sintonizacion Intradia de Golden Hours (09:00 y 11:00 UTC).
5. Invarianza de compatibilidad regresiva con la arquitectura previa.
=============================================================================
"""
import pytest
import pandas as pd
from engine.risk.risk_manager import RiskManager
from engine.backtest.unified_backtest_engine import UnifiedBacktestEngine


def test_sop46_weekly_alpha_cycle_modulation():
    """Valida la modulacion de riesgo por dias de la semana segun liquidez institucional."""
    # Lunes neutro
    mult_mon = RiskManager.calculate_alpha_tier_sizing(
        "NEARUSDT", confluence_score=75.0, day_of_week="Monday", apply_alpha_cycle=True
    )
    # Martes expansion (1.20x)
    mult_tue = RiskManager.calculate_alpha_tier_sizing(
        "NEARUSDT", confluence_score=75.0, day_of_week="Tuesday", apply_alpha_cycle=True
    )
    # Miercoles expansion (1.20x)
    mult_wed = RiskManager.calculate_alpha_tier_sizing(
        "NEARUSDT", confluence_score=75.0, day_of_week="Wednesday", apply_alpha_cycle=True
    )
    # Viernes defensa (0.80x)
    mult_fri = RiskManager.calculate_alpha_tier_sizing(
        "NEARUSDT", confluence_score=75.0, day_of_week="Friday", apply_alpha_cycle=True
    )
    # Domingo bajo volumen (0.70x)
    mult_sun = RiskManager.calculate_alpha_tier_sizing(
        "NEARUSDT", confluence_score=75.0, day_of_week="Sunday", apply_alpha_cycle=True
    )

    base = 1.25  # NEAR base tier
    assert mult_tue == pytest.approx(round(base * 1.20, 2), abs=0.02)
    assert mult_wed == pytest.approx(round(base * 1.20, 2), abs=0.02)
    assert mult_fri == pytest.approx(round(base * 0.80, 2), abs=0.02)
    assert mult_sun == pytest.approx(round(base * 0.70, 2), abs=0.02)
    assert mult_tue > mult_mon > mult_fri > mult_sun


def test_sop47_alpha_trinity_conviction_boost():
    """Valida el multiplicador Kelly 1.20x exclusivo para BNB, SOL y FET."""
    # Trinidad del Alfa
    bnb_boosted = RiskManager.calculate_alpha_tier_sizing("BNBUSDT", confluence_score=75.0, apply_trinity_boost=True)
    sol_boosted = RiskManager.calculate_alpha_tier_sizing("SOLUSDT", confluence_score=75.0, apply_trinity_boost=True)
    fet_boosted = RiskManager.calculate_alpha_tier_sizing("FETUSDT", confluence_score=75.0, apply_trinity_boost=True)

    bnb_base = RiskManager.calculate_alpha_tier_sizing("BNBUSDT", confluence_score=75.0, apply_trinity_boost=False)
    sol_base = RiskManager.calculate_alpha_tier_sizing("SOLUSDT", confluence_score=75.0, apply_trinity_boost=False)
    fet_base = RiskManager.calculate_alpha_tier_sizing("FETUSDT", confluence_score=75.0, apply_trinity_boost=False)

    assert bnb_boosted == pytest.approx(round(bnb_base * 1.20, 2), abs=0.02)
    assert sol_boosted == pytest.approx(round(sol_base * 1.20, 2), abs=0.02)
    assert fet_boosted == pytest.approx(round(fet_base * 1.20, 2), abs=0.02)

    # Activo no perteneciente a la trinidad no debe recibir el boost
    avax_boosted = RiskManager.calculate_alpha_tier_sizing("AVAXUSDT", confluence_score=75.0, apply_trinity_boost=True)
    avax_base = RiskManager.calculate_alpha_tier_sizing("AVAXUSDT", confluence_score=75.0, apply_trinity_boost=False)
    assert avax_boosted == avax_base


def test_sop49_golden_hours_tuning():
    """Valida el bono de +15% de aceleracion en 09:00 y 11:00 UTC."""
    mult_09 = RiskManager.calculate_alpha_tier_sizing("SOLUSDT", confluence_score=75.0, hour_utc=9, apply_golden_hours=True)
    mult_11 = RiskManager.calculate_alpha_tier_sizing("SOLUSDT", confluence_score=75.0, hour_utc=11, apply_golden_hours=True)
    mult_12 = RiskManager.calculate_alpha_tier_sizing("SOLUSDT", confluence_score=75.0, hour_utc=12, apply_golden_hours=True)

    assert mult_09 == pytest.approx(1.15, abs=0.02)
    assert mult_11 == pytest.approx(1.15, abs=0.02)
    assert mult_12 == pytest.approx(1.00, abs=0.02)
    assert mult_09 > mult_12


def test_backward_compatibility_defaults():
    """Verifica que sin flags activados, las salidas sean 100% identicas al modelo base."""
    assert RiskManager.calculate_alpha_tier_sizing("BNBUSDT", 75.0) == 1.25
    assert RiskManager.calculate_alpha_tier_sizing("SOLUSDT", 75.0) == 1.00
    assert RiskManager.calculate_alpha_tier_sizing("FETUSDT", 75.0) == 1.40
    assert RiskManager.calculate_alpha_tier_sizing("RENDERUSDT", 75.0) == 0.60
    assert RiskManager.calculate_alpha_tier_sizing("BTCUSDT", 75.0) == 0.75


def test_sop48_ker_computation_in_backtest_engine():
    """Verifica que el motor pre-calcule Kaufman Efficiency Ratio (KER) y soporte elastic runner."""
    engine = UnifiedBacktestEngine()
    trades_elastic = engine.run_single_asset("BTCUSDT", interval="15m", enable_elastic_runner=True)
    trades_static = engine.run_single_asset("BTCUSDT", interval="15m", enable_elastic_runner=False)

    assert len(trades_elastic) > 0
    assert len(trades_static) > 0
    for t in trades_elastic:
        assert "ker" in t
        assert "is_elastic" in t
        assert t["ker"] >= 0.0
