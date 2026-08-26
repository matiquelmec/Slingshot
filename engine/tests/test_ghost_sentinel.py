"""
engine/tests/test_ghost_sentinel.py
=============================================================================
Suite de Pruebas Unitarias y Métricas de Seguridad para Ghost Sentinel Macro
=============================================================================
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock
from engine.indicators.ghost_data import (
    _compute_bias,
    refresh_ghost_data,
    get_ghost_state,
    GhostState
)
from engine.router.gatekeeper import SignalGatekeeper, GatekeeperContext
from engine.risk.risk_manager import RiskManager

@pytest.mark.asyncio
async def test_ghost_bias_computation_rules():
    """Valida las reglas deterministas de sesgo macro."""
    # 1. Pánico Extremo + DXY Alcista en Altcoins -> Debe bloquear Longs
    bias, block_longs, block_shorts, reason = _compute_bias(
        symbol="SOLUSDT",
        fng=18,
        btcd=58.0,
        funding=-0.0002,
        dxy="BULLISH",
        nasdaq="BEARISH",
        news_sentiment=0.30,
        active_event="Crisis de Liquidez"
    )
    assert block_longs is True
    assert bias == "BLOCK_LONGS"
    assert "DXY Alcista" in reason or "SENTIMIENTO BAJISTA" in reason

    # 2. Sentimiento Alcista en Oro durante NASDAQ Bearish
    bias_gold, block_longs_g, block_shorts_g, _ = _compute_bias(
        symbol="PAXGUSDT",
        fng=60,
        btcd=52.0,
        funding=0.0001,
        dxy="BEARISH",
        nasdaq="BEARISH",
        news_sentiment=0.70,
        active_event="Vuelo a la Calidad"
    )
    assert block_shorts_g is True
    assert bias_gold in ("BULLISH", "BLOCK_SHORTS")

@pytest.mark.asyncio
async def test_gatekeeper_macro_veto_execution():
    """Valida que el Gatekeeper vete automáticamente órdenes contra el macro bias."""
    risk_mgr = RiskManager(account_balance=100_000.0, base_risk_pct=0.01)
    gatekeeper = SignalGatekeeper(risk_mgr)
    
    # Crear señales candidatas
    signals = [
        {"asset": "SOLUSDT", "signal_type": "LONG", "price": 180.0, "stop_loss": 178.0},
        {"asset": "BTCUSDT", "signal_type": "SHORT", "price": 95000.0, "stop_loss": 95800.0}
    ]
    
    # Contexto con bloqueo de Longs por Ghost Sentinel
    context = GatekeeperContext(
        ghost_data={
            "data": {
                "block_longs": True,
                "block_shorts": False,
                "reason": "Miedo Extremo en Derivados (F&G < 20)"
            }
        }
    )
    
    # DataFrame mock mínimo
    import pandas as pd
    df_mock = pd.DataFrame({
        "timestamp": [pd.Timestamp.now(tz="UTC")],
        "open": [180.0], "high": [181.0], "low": [179.0], "close": [180.0], "volume": [1000.0]
    })
    
    res = await gatekeeper.process(
        signals=signals,
        df=df_mock,
        smc_map={},
        key_levels=[],
        interval="15m",
        context=context,
        silent=True
    )
    
    # Debe haber bloqueado la orden LONG de SOLUSDT por el centinela macro
    blocked_vetos = [s.get("gatekeeper_veto", "") for s in res.blocked]
    assert any("GHOST_SENTINEL" in v for v in blocked_vetos)

@pytest.mark.asyncio
async def test_ghost_data_hydration_and_fallback():
    """Valida que refresh_ghost_data responda sin lanzar excepciones."""
    state = await refresh_ghost_data("BTCUSDT", global_only=True)
    assert isinstance(state, GhostState)
    assert state.fear_greed_value >= 0
    assert state.btc_dominance >= 0.0
