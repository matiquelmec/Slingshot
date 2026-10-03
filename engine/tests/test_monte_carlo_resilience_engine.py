"""
engine/tests/test_monte_carlo_resilience_engine.py
==================================================
Pruebas unitarias para el motor de simulación Monte Carlo y Value-at-Risk (SOP-107).
"""

import pytest
import numpy as np
from engine.analytics.monte_carlo_resilience_engine import (
    MonteCarloResilienceEngine,
    get_default_monte_carlo_resilience_report,
)


def test_monte_carlo_determinism_and_shapes():
    """Valida determinismo estricto mediante semilla y consistencia de dimensiones."""
    engine = MonteCarloResilienceEngine()
    metrics1 = engine.run_simulation(iterations=2000, horizon_trades=50, seed=123)
    metrics2 = engine.run_simulation(iterations=2000, horizon_trades=50, seed=123)

    assert metrics1.median_final_net_r == metrics2.median_final_net_r
    assert metrics1.var_99_r == metrics2.var_99_r
    assert metrics1.p95_max_drawdown_r == metrics2.p95_max_drawdown_r
    assert len(metrics1.equity_cones["steps"]) == 10
    assert len(metrics1.equity_cones["p50"]) == 10


def test_monte_carlo_var_and_risk_of_ruin_invariance():
    """Valida que las métricas de cola (VaR 99%, CVaR) cumplan invariantes matemáticas."""
    engine = MonteCarloResilienceEngine()
    metrics = engine.run_simulation(iterations=5000, horizon_trades=100, seed=42)

    # VaR 99% debe ser menor o igual a VaR 95% (cola más lejana a la izquierda)
    assert metrics.var_99_r <= metrics.var_95_r
    # CVaR (Expected Shortfall) debe ser menor o igual a VaR 99% (promedio de la cola extrema)
    assert metrics.cvar_99_r <= metrics.var_99_r

    # Drawdown percentil 99 debe ser mayor o igual al percentil 95
    assert metrics.p99_max_drawdown_r >= metrics.p95_max_drawdown_r

    # Riesgo de Ruina de capital inicial bajo (< 3.0% para Slingshot SSoT sin apalancamiento)
    assert metrics.risk_of_ruin_pct < 3.0
    # Probabilidad de ganancia a 100 trades >= 95%
    assert metrics.probability_of_profit_pct >= 95.0
    assert metrics.solvency_grade == "TIER_1_AAA"


def test_monte_carlo_report_helper():
    """Valida la función exportadora para contratos full-stack."""
    report = get_default_monte_carlo_resilience_report()
    assert report["iterations"] == 10000
    assert report["horizonTrades"] == 100
    assert "equityCones" in report
    assert report["solvencyGrade"] == "TIER_1_AAA"
    assert report["riskOfRuinPct"] < 3.0
    assert len(report["summaryReport"]) > 20
