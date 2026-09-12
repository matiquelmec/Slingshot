"""
engine/tests/test_aiq_blueprint_orchestration.py
================================================
Suite de Pruebas Unitarias para la Arquitectura NVIDIA AI-Q Blueprint:
1. Conector Relacional Multi-Tabla (Esquema Kumo Relational).
2. Memoria Semántica Vectorial con Similitud Coseno (nemotron-3-embed-1b).
3. Enrutador Agéntico Multi-Modelo con Failover Automático.
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np

from engine.aiq.config import aiq_settings
from engine.aiq.relational_connector import AIQRelationalConnector
from engine.aiq.semantic_memory import AIQSemanticMemory
from engine.aiq.agent_router import AIQAgentRouter


def test_aiq_config_loading():
    """Valida que los modelos canónicos del catálogo NVIDIA NIM estén configurados."""
    assert "nemotron-3.5-lightning" in aiq_settings.MODEL_POST_MORTEM_FAST
    assert "deepseek-v4-flash" in aiq_settings.MODEL_POST_MORTEM_FALLBACK
    assert "nemotron-3-embed-1b" in aiq_settings.MODEL_EMBEDDINGS
    assert "nemotron-3-ultra-550b" in aiq_settings.MODEL_MACRO_SYNTHESIZER
    assert "kumo-relational" in aiq_settings.MODEL_RELATIONAL_PREDICTOR


def test_aiq_relational_connector(tmp_path):
    """Verifica la extracción multi-tabla y el cálculo de Win Rate relacional."""
    connector = AIQRelationalConnector()
    features = connector.build_cross_table_features(
        target_symbol="BTCUSDT",
        target_regime="BULL_EXPANSION",
        active_factors=["order_blocks", "fvg", "liquidity_sweep"]
    )

    assert "predicted_win_prob" in features
    assert 0.0 <= features["predicted_win_prob"] <= 1.0
    assert "confidence" in features
    assert "relational_edge" in features


@pytest.mark.asyncio
async def test_aiq_semantic_memory_cosine_similarity():
    """Verifica la generación de embeddings y búsqueda por similitud vectorial."""
    memory = AIQSemanticMemory()

    # Almacenar dos eventos
    await memory.store_event(
        event_id="EVT_01",
        description="Falso quiebre en resistencia 15m durante la sesión de Londres con barrido de liquidez",
        metadata={"asset": "BTCUSDT", "tag": "LIQUIDITY_SWEEP"}
    )
    await memory.store_event(
        event_id="EVT_02",
        description="Expansión alcista sostenida en tendencia impulsada por fuerte volumen en NY",
        metadata={"asset": "ETHUSDT", "tag": "TREND_EXPANSION"}
    )

    # Generar vector para búsqueda similar
    query_vec = await memory.generate_embedding("barrido de liquidez en falso quiebre Londres")
    similar = memory.find_similar_events(query_vec, top_k=2, min_similarity=0.10)

    assert len(similar) >= 1
    assert similar[0]["id"] == "EVT_01" or "LIQUIDITY_SWEEP" in similar[0]["metadata"]["tag"]


@pytest.mark.asyncio
async def test_aiq_agent_router_deterministic_fallback():
    """Verifica el fallback determinístico ante caídas de red o falta de API Key."""
    router = AIQAgentRouter()
    
    # 1. Post-Mortem rápido
    res_pm = await router.execute_fast_post_mortem("Simulación de trade perdedor en SOLUSDT")
    assert isinstance(res_pm, dict)
    assert "loss_category" in res_pm
    assert "apply_veto" in res_pm

    # 2. Síntesis macro semanal
    tear_sheet_mock = {
        "period": "Semana 37 - 2026",
        "total_trades": 18,
        "win_rate": 0.61,
        "ftmo_equity": 98500.0,
        "bitunix_equity": 820.0
    }
    res_macro = await router.execute_weekly_portfolio_audit(tear_sheet_mock)
    assert isinstance(res_macro, dict)
    assert "portfolio_health" in res_macro
    assert "ftmo_risk_recommendation" in res_macro
