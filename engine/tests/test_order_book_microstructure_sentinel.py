"""
engine/tests/test_order_book_microstructure_sentinel.py
=======================================================
Pruebas unitarias para el Centinela de Microestructura y Libro L2 (SOP-108).
"""

import pytest
from engine.analytics.order_book_microstructure_sentinel import (
    OrderBookMicrostructureSentinel,
    get_canonical_universe_l2_summary,
)


def test_order_book_balanced_approval():
    """Valida que un libro profundo y balanceado apruebe la orden."""
    sentinel = OrderBookMicrostructureSentinel(max_spread_bps=8.0, min_long_obi=-0.25)
    bids = [(100.0 - i * 0.1, 50.0) for i in range(20)]
    asks = [(100.02 + i * 0.1, 50.0) for i in range(20)]

    res = sentinel.audit_l2_book("SOLUSDT", "LONG", bids, asks)
    assert res.is_approved is True
    assert res.veto_reason is None
    assert abs(res.obi_score) < 0.10
    assert res.effective_spread_bps < 3.0
    assert res.recommended_action == "PROCEED_ORDER_DISPATCH"


def test_order_book_veto_by_heavy_ask_imbalance():
    """Valida veto en LONG cuando existe un muro masivo vendedor pasivo (OBI < -0.35)."""
    sentinel = OrderBookMicrostructureSentinel(min_long_obi=-0.25)
    bids = [(100.0 - i * 0.1, 10.0) for i in range(20)]
    asks = [(100.02 + i * 0.1, 100.0) for i in range(20)]  # 10x más volumen vendedor

    res = sentinel.audit_l2_book("FETUSDT", "LONG", bids, asks)
    assert res.is_approved is False
    assert "OBI_VENTA_DOMINANTE" in res.veto_reason
    assert res.obi_score < -0.35
    assert res.recommended_action == "HOLD_IN_SELECTIVE_PATIENCE"


def test_order_book_veto_by_wide_spread():
    """Valida veto por spread excesivo (ensanchamiento por iliquidez)."""
    sentinel = OrderBookMicrostructureSentinel(max_spread_bps=8.0)
    bids = [(100.0, 50.0)]
    asks = [(100.15, 50.0)]  # Spread de 15 bps (0.15%)

    res = sentinel.audit_l2_book("NEARUSDT", "LONG", bids, asks)
    assert res.is_approved is False
    assert "SPREAD_EXCESIVO" in res.veto_reason


def test_canonical_universe_l2_summary_helper():
    """Valida la función integradora para los 13 activos SSoT."""
    summaries = get_canonical_universe_l2_summary()
    assert len(summaries) == 13
    assert all("obiScore" in s for s in summaries)
    assert all("effectiveSpreadBps" in s for s in summaries)
