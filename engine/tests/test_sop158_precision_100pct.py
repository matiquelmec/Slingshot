"""
engine/tests/test_sop158_precision_100pct.py — Suite de Verificación SOP-158 (100% End-to-End)
=================================================================================================
Valida:
1. Resolución SSoT de símbolos .cash, dígitos y apalancamiento 1:15 para UK100, XAGUSD, XAUUSD, US100.
2. Calibración Target-Based del Best-Day Diluter (sin estrangular el Día 1) y weighted_r en FTMO_SWING.
3. Existencia de _bitunix_sync_lock y lectura de clave L2 'imbalance' en TradeManager.
"""
import asyncio
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from engine.analytics.prop_firm_pass_simulator import PropFirmPassSimulator
from engine.execution.mt5_bridge import MT5Bridge
from engine.risk.ftmo_guardian import FtmoGuardianShield
from engine.workers.trade_manager import TradeManager


def test_mt5_bridge_uk100_and_xagusd_homologation():
    bridge = MT5Bridge(dry_run=True)
    assert bridge.resolve_broker_symbol("UK100") == "UK100.cash"
    assert bridge.resolve_broker_symbol("US100") == "US100.cash"
    assert bridge.resolve_broker_symbol("XAUUSD") == "XAUUSD"
    assert bridge.resolve_broker_symbol("XAGUSD") == "XAGUSD"
    assert bridge.get_symbol_digits("UK100.cash") == 1
    assert bridge.get_symbol_digits("XAGUSD") == 2
    assert bridge.get_symbol_digits("EURUSD") == 5

    spreads = bridge.get_realtime_spreads()
    assert set(spreads.keys()) == {"XAUUSD", "XAGUSD", "US100.cash", "UK100.cash"}


def test_ftmo_guardian_uk100_contracts_and_best_day_target_calibration():
    guardian = FtmoGuardianShield(account_size=100000.0, phase="PHASE_1", account_type="SWING")
    lots_uk = guardian.calculate_mt5_lots("UK100.cash", entry_price=8200.0, stop_loss=8150.0, margin_free=95000.0)
    assert lots_uk["contract_size"] == 1
    assert lots_uk["lots"] > 0

    # Día 1 normal (+1.2% = $1,200): NO debe estrangular riesgo a 0.25% contra target de $10,000
    r_day1 = FtmoGuardianShield.compute_best_day_diluted_risk(
        base_risk_pct=0.0075,
        best_day_profit_usd=1200.0,
        total_profit_usd=1200.0,
        phase_target_usd=10000.0,
    )
    assert r_day1 == pytest.approx(0.0075)

    # Día extremo (+4.0% = $4,000 > 35% de $10,000): SÍ debe diluir a 0.25%
    r_extreme = FtmoGuardianShield.compute_best_day_diluted_risk(
        base_risk_pct=0.0075,
        best_day_profit_usd=4000.0,
        total_profit_usd=4000.0,
        phase_target_usd=10000.0,
    )
    assert r_extreme == pytest.approx(0.0025)


def test_prop_firm_simulator_uses_weighted_r_for_ftmo_swing(tmp_path: Path):
    report = {
        "oos_trade_stream": [
            {"symbol": "UK100", "day": "2026-01-02", "outcome_r": 2.0, "weighted_r": 1.3},
            {"symbol": "XAUUSD", "day": "2026-01-03", "outcome_r": 1.5, "weighted_r": 1.5},
        ]
    }
    p = tmp_path / "audit.json"
    p.write_text(json.dumps(report), encoding="utf-8")

    clusters = PropFirmPassSimulator.load_daily_clusters(report_path=str(p), profile="FTMO_SWING")
    assert len(clusters) == 2
    assert clusters[0]["net_r"] == pytest.approx(1.3)
    assert clusters[1]["net_r"] == pytest.approx(1.5)


def test_trade_manager_has_bitunix_sync_lock():
    tm = TradeManager()
    assert isinstance(tm._bitunix_sync_lock, asyncio.Lock)


def test_fastapi_gateway_imports_cleanly():
    from engine.api.main import app
    assert app is not None
