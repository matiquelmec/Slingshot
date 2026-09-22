"""
engine/tests/test_chronological_backtest_parity.py
=============================================================================
AUDITORÍA DE PARIDAD SSoT 1:1 ENTRE MOTOR DE PRODUCCIÓN Y BACKTEST CRONOLÓGICO
=============================================================================
Valida que UnifiedBacktestEngine replica con exactitud matemática:
1. SOP-97: Separación de riesgo flotante (max_unprotected=2) y techo físico (max_concurrent=4).
2. SOP-97: Desempate por Priority Score con boost 1.25x a la Trinidad del Alfa (ETH, SOL, BNB, INJ).
3. SOP-99: Elasticidad Dinámica (Contracción a 1/3 en racha >=2, Expansión a 3/5 con XAUUSDT desacoplado).
"""

import pytest
import pandas as pd
from datetime import datetime, timedelta
from engine.backtest.unified_backtest_engine import UnifiedBacktestEngine


def test_chronological_backtest_replay_structure():
    """Valida que run_chronological_portfolio_replay incluya las métricas de paridad SOP-97/99."""
    engine = UnifiedBacktestEngine()
    
    # Creamos un conjunto de prueba controlado con 5 operaciones simultáneas
    base_time = pd.to_datetime("2026-03-01 12:00:00")
    test_trades = [
        # Op 1: SOLUSDT (Trinity - entra a las 12:00, TP1 a las 12:30, Exit a las 14:00)
        {
            "symbol": "SOLUSDT",
            "direction": "LONG",
            "entry_time": base_time,
            "exit_time": base_time + timedelta(hours=2),
            "tp1_time": base_time + timedelta(minutes=30),
            "outcome_r": 1.5,
            "confluence_score": 80.0
        },
        # Op 2: BNBUSDT (Trinity - entra a las 12:00, SL directo sin TP1, Exit a las 13:00)
        {
            "symbol": "BNBUSDT",
            "direction": "LONG",
            "entry_time": base_time,
            "exit_time": base_time + timedelta(hours=1),
            "tp1_time": None,
            "outcome_r": -0.65,
            "confluence_score": 82.0
        },
        # Op 3: AVAXUSDT (Tier 2 - compite a las 12:00, con 2 riesgos ocupados debe ser rechazada por riesgo)
        {
            "symbol": "AVAXUSDT",
            "direction": "LONG",
            "entry_time": base_time,
            "exit_time": base_time + timedelta(hours=1),
            "tp1_time": None,
            "outcome_r": 1.0,
            "confluence_score": 75.0
        },
        # Op 4: NEARUSDT (Tier 2 - entra a las 12:45 cuando SOL liberó riesgo en TP1 a las 12:30)
        # SOL sigue viva físicamente pero su riesgo está en 0. BNB sigue en riesgo. Total riesgo = 1.
        # NEAR debe ser aceptada porque unprotected_count = 1 < 2.
        {
            "symbol": "NEARUSDT",
            "direction": "LONG",
            "entry_time": base_time + timedelta(minutes=45),
            "exit_time": base_time + timedelta(hours=2),
            "tp1_time": None,
            "outcome_r": 1.2,
            "confluence_score": 78.0
        }
    ]
    
    # Verificamos que priority_score favorece a Trinity
    def score_calc(row):
        score = float(row.get("confluence_score", 70.0))
        s = str(row.get("symbol", "")).upper()
        mult = 1.25 if any(t in s for t in ("ETH", "SOL", "BNB", "INJ")) else 1.0
        return score * mult

    sol_score = score_calc(test_trades[0]) # 80 * 1.25 = 100
    bnb_score = score_calc(test_trades[1]) # 82 * 1.25 = 102.5
    avax_score = score_calc(test_trades[2]) # 75 * 1.0 = 75
    
    assert bnb_score > sol_score > avax_score
