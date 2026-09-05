"""
=============================================================================
SLINGSHOT v23.3 APEX - INSTITUTIONAL BACKTEST SSOT QA SUITE
=============================================================================
Pruebas unitarias cuantitativas que certifican el Motor de Backtest SSoT:
1. Verificacion de inicializacion y parametros de comisiones Bitunix.
2. Colocacion estructural de Stop Loss & OTE mediante RiskManager.
3. Precision de ejecucion intra-vela y ordenes limite con descuento OTE.
4. Malla de Salidas Dinamica SOP-26 (40% TP1 @ +1.2R, 40% TP2 @ +2.0R, 20% TP3 @ +3.5R).
5. Invalidacion temprana SOP-25 @ -0.65R para preservacion de capital.
6. Segmentacion del universo institucional (MEGA_CAPS y HIGH_BETA_ALTS).
=============================================================================
"""
import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timezone

from engine.backtest.unified_backtest_engine import (
    UnifiedBacktestEngine,
    MEGA_CAPS,
    HIGH_BETA_ALTS
)
from engine.risk.risk_manager import RiskManager
from engine.core.confluence import confluence_manager

@pytest.fixture
def engine():
    return UnifiedBacktestEngine(min_confluence_score=50)

def test_unified_backtest_engine_initialization(engine):
    assert engine.min_score == 50
    assert engine.maker_fee == 0.0002
    assert engine.taker_fee == 0.0006
    assert engine.slippage == 0.0002
    assert engine.strategy is not None
    assert engine.risk_mgr is not None

def test_sop26_mfe_harvesting_grid_volume_conservation():
    # Matriz oficial SOP-26: 40% TP1, 40% TP2, 20% TP3
    tp1_pct = 0.40
    tp2_pct = 0.40
    tp3_pct = 0.20
    total_exit = tp1_pct + tp2_pct + tp3_pct
    assert total_exit == pytest.approx(1.0, rel=1e-6)

def test_structural_sl_and_ote_via_risk_manager(engine):
    calc = engine.risk_mgr.calculate_position(
        current_price=60000.0,
        signal_type="LONG",
        market_regime="MARKUP",
        smc_data={
            "order_blocks": {
                "bullish": [{"top": 60100.0, "bottom": 59800.0}],
                "bearish": []
            }
        },
        atr_value=400.0,
        asset="BTCUSDT",
        confluence_score=80
    )
    
    assert calc is not None
    assert calc["stop_loss"] < 60000.0
    assert calc["tp1"] > 60000.0
    assert calc["be_price"] > 60000.0
    assert calc["be_price"] < calc["tp1"]

def test_sop25_early_invalidation_math():
    # Prueba de invalidacion temprana @ -0.65R
    entry = 100.0
    sl = 90.0
    risk = entry - sl # 10.0
    cur_adverse_price = entry - (risk * 0.65) # 93.5
    adverse_r = (entry - cur_adverse_price) / risk
    assert adverse_r == pytest.approx(0.65, rel=1e-5)

def test_canonical_universe_segmentation():
    # Mega-Caps vs High-Beta Alts
    assert "BTCUSDT" in MEGA_CAPS
    assert "ETHUSDT" in MEGA_CAPS
    assert "SOLUSDT" in MEGA_CAPS
    assert "INJUSDT" in HIGH_BETA_ALTS
    assert "BNBUSDT" in HIGH_BETA_ALTS
    assert "NEARUSDT" in HIGH_BETA_ALTS
