"""
engine/tests/test_funding_rate_drag_sentinel.py
===============================================
Pruebas unitarias para el Escudo de Funding Rates y Carry Drag (SOP-109).
"""

import pytest
from engine.analytics.funding_rate_drag_sentinel import (
    FundingRateDragSentinel,
    get_canonical_universe_funding_summary,
)


def test_funding_sentinel_normal_state():
    """Valida estado NORMAL cuando el funding es bajo y sostenible."""
    sentinel = FundingRateDragSentinel()
    res = sentinel.audit_position_carry(
        asset="BTCUSDT",
        direction="LONG",
        funding_rate_8h=0.0001,  # 0.01%
        duration_days=3.0,
        position_notional_usd=10000.0,
        initial_dollar_risk=250.0,
    )
    assert res.status == "NORMAL"
    assert res.recommended_chandelier_multiplier == 1.5
    assert "MANTENER_TRAILING" in res.action_directive


def test_funding_sentinel_warning_tighten():
    """Valida que apriete el trailing a 1.0x ATR cuando el funding supera 50% APR."""
    sentinel = FundingRateDragSentinel(warning_apr_pct=50.0)
    res = sentinel.audit_position_carry(
        asset="SOLUSDT",
        direction="LONG",
        funding_rate_8h=0.0005,  # 0.05% cada 8h -> ~54.75% APR
        duration_days=4.0,
        position_notional_usd=10000.0,
        initial_dollar_risk=250.0,
    )
    assert res.status == "WARNING_TIGHTEN"
    assert res.recommended_chandelier_multiplier == 1.0
    assert "APRETAR_TRAILING_A_1.0X" in res.action_directive


def test_funding_sentinel_critical_harvest():
    """Valida alerta crítica cuando el drag o APR supera 75%."""
    sentinel = FundingRateDragSentinel(critical_apr_pct=75.0)
    res = sentinel.audit_position_carry(
        asset="FETUSDT",
        direction="LONG",
        funding_rate_8h=0.0008,  # 0.08% cada 8h -> ~87.6% APR
        duration_days=7.0,
        position_notional_usd=10000.0,
        initial_dollar_risk=250.0,
    )
    assert res.status == "CRITICAL_HARVEST"
    assert "FORZAR_TOMA_DE_GANANCIAS" in res.action_directive


def test_canonical_universe_funding_summary_helper():
    """Valida helper para los 13 activos canónicos SSoT."""
    summaries = get_canonical_universe_funding_summary()
    assert len(summaries) == 13
    assert all("annualizedFundingAprPct" in s for s in summaries)
    assert all("recommendedChandelierMultiplier" in s for s in summaries)
