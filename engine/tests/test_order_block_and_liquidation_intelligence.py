"""
engine/tests/test_order_block_and_liquidation_intelligence.py
=============================================================
Pruebas cuantitativas de grado industrial para SOP-112:
1. Graduación de Order Blocks (RVOL, strength_score, touch_count, is_virgin).
2. Ponderación adaptativa en ConfluenceManager.
3. Confluencia Magnética Dual (OB + Cluster de Liquidación masiva >80%).
4. Reporte consolidado del Centinela para los 13 activos canónicos SSoT.
"""

import pytest
import pandas as pd
import numpy as np
from engine.indicators.structure import identify_order_blocks, extract_smc_coordinates
from engine.core.confluence import ConfluenceManager
from engine.analytics.order_block_liquidity_sentinel import (
    OrderBlockLiquiditySentinel,
    get_canonical_universe_ob_liquidity_summary,
)


def test_order_block_strength_and_virgin_tracking():
    """Valida que los Order Blocks registren su volumen relativo, fuerza, toques y condición de virgen."""
    candles = []
    base_price = 100.0

    # 1. Velas preliminares para estabilizar medias móviles
    for i in range(25):
        candles.append({
            "timestamp": pd.Timestamp("2026-05-01 10:00:00") + pd.Timedelta(minutes=15 * i),
            "open": base_price,
            "high": base_price + 0.5,
            "low": base_price - 0.5,
            "close": base_price + 0.1,
            "volume": 1000.0,
        })

    # 2. Vela previa bajista (Order Block origin) con volumen institucional (2.5x)
    candles.append({
        "timestamp": pd.Timestamp("2026-05-01 16:15:00"),
        "open": 100.0,
        "high": 100.2,
        "low": 98.0,
        "close": 98.5,
        "volume": 2500.0,
    })

    # 3. Vela de expansión alcista fuerte (BOS/Imbalance)
    candles.append({
        "timestamp": pd.Timestamp("2026-05-01 16:30:00"),
        "open": 98.6,
        "high": 103.0,
        "low": 98.6,
        "close": 102.8,
        "volume": 3000.0,
    })

    # 4. Vela siguiente que NO penetra el bloque (bloque virgen)
    candles.append({
        "timestamp": pd.Timestamp("2026-05-01 16:45:00"),
        "open": 102.8,
        "high": 104.0,
        "low": 101.5,  # Mínimo no toca el techo del bloque (100.2)
        "close": 103.5,
        "volume": 1200.0,
    })

    df = pd.DataFrame(candles)
    df_analyzed = identify_order_blocks(df)
    coords = extract_smc_coordinates(df_analyzed)

    bull_obs = coords["order_blocks"]["bullish"]
    assert len(bull_obs) > 0, "Debe detectar al menos un Order Block alcista"

    last_ob = bull_obs[-1]
    assert last_ob["is_virgin"] is True
    assert last_ob["touch_count"] == 0
    assert last_ob["volume_ratio"] >= 1.8
    assert last_ob["strength_score"] >= 80.0
    assert last_ob["top"] > last_ob["bottom"]


def test_confluence_manager_adaptive_ob_weighting():
    """Valida que un OB virgen de alto volumen reciba mayor puntaje que un OB sobre-testeado."""
    manager = ConfluenceManager()
    history = pd.DataFrame([
        {"close": 100.0, "high": 100.5, "low": 99.5, "volume": 1000.0, "timestamp": "2026-05-01 12:00:00"}
    ] * 20)
    history["timestamp"] = pd.to_datetime(history["timestamp"])

    # Escenario A: OB Virgen de alta convicción
    ob_virgin = {
        "top": 100.5,
        "bottom": 99.0,
        "is_virgin": True,
        "touch_count": 0,
        "volume_ratio": 2.2,
        "strength_score": 90.0,
    }
    res_virgin = manager.evaluate_signal(
        df=history,
        signal={"price": 100.0, "type": "LONG", "timestamp": "2026-05-01 12:00:00"},
        smc_map={"order_blocks": {"bullish": [ob_virgin], "bearish": []}, "fvgs": {"bullish": [], "bearish": []}},
    )

    # Escenario B: OB sobre-testeado con fatiga (3 toques)
    ob_exhausted = {
        "top": 100.5,
        "bottom": 99.0,
        "is_virgin": False,
        "touch_count": 3,
        "volume_ratio": 1.1,
        "strength_score": 60.0,
    }
    res_exhausted = manager.evaluate_signal(
        df=history,
        signal={"price": 100.0, "type": "LONG", "timestamp": "2026-05-01 12:00:00"},
        smc_map={"order_blocks": {"bullish": [ob_exhausted], "bearish": []}, "fvgs": {"bullish": [], "bearish": []}},
    )

    score_virgin = res_virgin.get("score", 0)
    score_exhausted = res_exhausted.get("score", 0)
    assert score_virgin > score_exhausted, "El OB virgen debe tener mayor puntuación que el bloque agotado"


def test_confluence_manager_dual_magnetic_liquidity():
    """Valida que un cluster de liquidación >80% alineado con un Order Block active la Confluencia Magnética Dual."""
    manager = ConfluenceManager()
    history = pd.DataFrame([
        {"close": 100.0, "high": 100.5, "low": 99.5, "volume": 1000.0, "timestamp": "2026-05-01 12:00:00"}
    ] * 20)
    history["timestamp"] = pd.to_datetime(history["timestamp"])

    ob_target = {"top": 101.5, "bottom": 100.5}  # En zona de TP cercano
    liq_clusters = [{"price": 100.8, "strength": 90, "type": "SHORT_LIQ"}]  # Dentro del bloque y >80%

    res = manager.evaluate_signal(
        df=history,
        signal={"price": 100.0, "type": "LONG", "timestamp": "2026-05-01 12:00:00"},
        liquidation_clusters=liq_clusters,
        smc_map={"order_blocks": {"bullish": [ob_target], "bearish": []}, "fvgs": {"bullish": [], "bearish": []}},
    )

    checklist = res.get("checklist", [])
    liq_check = [c for c in checklist if c.get("factor") == "Liq Clusters"]
    assert len(liq_check) > 0
    assert liq_check[0]["status"] == "ELITE"
    assert "Dual" in liq_check[0]["detail"]


def test_ob_liquidity_sentinel_canonical_universe():
    """Valida que el centinela genere el sumario de los 13 activos canónicos sin errores."""
    summary = get_canonical_universe_ob_liquidity_summary()
    assert len(summary) == 13
    assert all("asset" in item for item in summary)
    assert all("dominantOb" in item for item in summary)
    assert all("weightingRating" in item for item in summary)
    assert all(item["weightingRating"] in ["OPTIMA_INSTITUTIONAL", "FUERTE", "CAUTELA_EXHAUSTION"] for item in summary)
