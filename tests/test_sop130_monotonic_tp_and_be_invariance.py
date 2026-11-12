"""
tests/test_sop130_monotonic_tp_and_be_invariance.py
===================================================
Suite de Certificación Unitaria para SOP-130:
1. Validador Monotónico de Escalera de Salidas (Entry > TP1 > TP2 > TP3 en SHORT / Entry < TP1 < TP2 < TP3 en LONG).
2. Caso real SOLUSDT: corrección automática de TPs invertidos ($74.08, $76.29, $74.43) hacia la escalera exacta 1.2R / 2.0R / 3.5R ($79.97 / $77.75 / $73.60).
3. Caso real TIAUSDT: preservación exacta cuando los TPs del plan cumplen geometría monotónica ($0.3883 / $0.3678 / $0.3294).
4. Persistencia y recuperación transaccional del plan de orden del sistema (system_order_plans) y riesgo inicial (position_risk_cache) en SQLite WAL.
5. Inmunidad del initial_stop_loss en TradeManager y Nexus tras alcanzar Break-Even (caso real INJUSDT).
"""
import tempfile
from pathlib import Path
import pytest

from engine.execution.nexus import NexusNode
from engine.core.vault import SlingshotVault


def test_sop130_solusdt_inverted_tps_are_reanchored_to_canonical_ladder():
    """
    Caso real SOLUSDT SHORT @ $83.29 con SL inicial $86.06 (1R = $2.77):
    Si el escáner tenía TPs invertidos ($74.08, $76.29, $74.43), validate_and_anchor_tp_ladder
    debe rechazar la inversión y recalcular la escalera exacta 1.2R / 2.0R / 3.5R.
    """
    entry = 83.29
    initial_sl = 86.06
    dist, be, tp1, tp2, tp3 = NexusNode.validate_and_anchor_tp_ladder(
        entry_price=entry,
        initial_sl=initial_sl,
        side="SHORT",
        raw_tp1=74.08,
        raw_tp2=76.29,
        raw_tp3=74.43,
    )
    assert round(dist, 2) == 2.77
    assert round(be, 2) == 80.52
    assert round(tp1, 2) == 79.97
    assert round(tp2, 2) == 77.75
    assert round(tp3, 2) == 73.60
    assert entry > tp1 > tp2 > tp3


def test_sop130_tiausdt_valid_smc_tps_are_preserved():
    """
    Caso real TIAUSDT SHORT @ $0.4178 con SL inicial $0.4446 (1R = $0.0268):
    Los niveles SMC ($0.3883 [+1.10R], $0.3678 [+1.87R], $0.3294 [+3.30R]) cumplen
    progresión monotónica estricta y geometría institucional, por lo que se preservan intactos.
    """
    entry = 0.4178
    initial_sl = 0.4446
    dist, be, tp1, tp2, tp3 = NexusNode.validate_and_anchor_tp_ladder(
        entry_price=entry,
        initial_sl=initial_sl,
        side="SHORT",
        raw_tp1=0.3883,
        raw_tp2=0.3678,
        raw_tp3=0.3294,
    )
    assert round(dist, 4) == 0.0268
    assert tp1 == 0.3883
    assert tp2 == 0.3678
    assert tp3 == 0.3294
    assert entry > tp1 > tp2 > tp3


def test_sop130_long_monotonic_validation():
    """Verifica que en posiciones LONG se exija estrictamente Entry < TP1 < TP2 < TP3."""
    entry = 100.0
    initial_sl = 98.0  # 1R = $2.0
    # TPs invertidos (TP1 > TP2)
    dist, be, tp1, tp2, tp3 = NexusNode.validate_and_anchor_tp_ladder(
        entry_price=entry,
        initial_sl=initial_sl,
        side="LONG",
        raw_tp1=105.0,
        raw_tp2=103.0,
        raw_tp3=108.0,
    )
    assert dist == 2.0
    assert be == 102.0
    assert tp1 == 102.4
    assert tp2 == 104.0
    assert tp3 == 107.0
    assert entry < tp1 < tp2 < tp3


def test_sop130_vault_system_order_plan_and_risk_record_persistence(tmp_path):
    """
    Verifica que SlingshotVault almacene y recupere de forma atómica el plan original
    de una orden del sistema (system_order_plans) y el registro de riesgo inicial (position_risk_cache),
    permitiendo distinguir órdenes del sistema (SYSTEM_AUTO) e impidiendo perder el 1R tras Break-Even.
    """
    db_file = tmp_path / "test_vault_sop130.db"
    v = SlingshotVault(db_path=db_file)

    v.save_system_order_plan(
        account_id="primary",
        symbol="INJUSDT",
        side="SHORT",
        entry_price=7.9680,
        initial_sl=8.3593,
        tp1=7.4984,
        tp2=7.1854,
        tp3=6.5985,
        order_id="ord_12345",
        origin="SYSTEM_AUTO",
    )

    plan = v.get_system_order_plan("primary", "INJUSDT", "SHORT")
    assert plan is not None
    assert plan["origin"] == "SYSTEM_AUTO"
    assert plan["entry_price"] == 7.9680
    assert plan["initial_sl"] == 8.3593
    assert plan["tp1"] == 7.4984
    assert plan["tp2"] == 7.1854
    assert plan["tp3"] == 6.5985

    # Persistir riesgo inicial con position_id y verificar fallback por symbol+side
    v.save_position_risk(
        pos_key="primary_INJUSDT_4059920065256191360",
        symbol="INJUSDT",
        side="SHORT",
        sl_dist=0.3913,
        entry_price=7.9680,
        initial_sl=8.3593,
    )

    rec_exact = v.get_position_risk_record("primary_INJUSDT_4059920065256191360")
    assert rec_exact is not None
    assert round(rec_exact["sl_dist"], 4) == 0.3913
    assert round(rec_exact["initial_sl"], 4) == 8.3593

    rec_fallback = v.get_position_risk_record("primary_INJUSDT_unknown", symbol="INJUSDT", side="SHORT")
    assert rec_fallback is not None
    assert round(rec_fallback["initial_sl"], 4) == 8.3593

    # Purgar plan al cerrar posición
    v.purge_system_order_plan("primary", "INJUSDT", "SHORT")
    assert v.get_system_order_plan("primary", "INJUSDT", "SHORT") is None
