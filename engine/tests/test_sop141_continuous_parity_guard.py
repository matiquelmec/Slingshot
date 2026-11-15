"""
engine/tests/test_sop141_continuous_parity_guard.py
===================================================
SUITE DE CONTRATO CI/CD — PROTOCOLO SOP-141 DE PARIDAD CONTINUA SSoT
Garantiza sincronización 1:1 entre:
  - engine/core/strategy_ssot.py
  - MarketScanner & NexusNode (producción)
  - UnifiedBacktestEngine & chronological_backtest_report.json
  - MonteCarloResilienceEngine (teórico y realista SOP-119)
  - src/features/backtest-metrics/actions.ts (UI)
"""

import json
import os
import re
from datetime import datetime, timezone

import pytest

from engine.core.strategy_ssot import (
    APPROVED_SCALP_15M_EXECUTION,
    APPROVED_SWING_1H_EXECUTION,
    BASE_MAX_UNPROTECTED_RISK_SLOTS,
    LONG_ONLY_STRUCTURAL_ASSETS_SOP137,
    PRUNED_NEGATIVE_EXPECTANCY_ASSETS,
    SHORT_ONLY_ASYMMETRIC_ASSETS_SOP137,
    TOXIC_UTC_HOURS_SOP137,
    calculate_priority_score,
    is_directional_setup_allowed_sop137,
    is_quant_approved_pair,
)
from engine.analytics.monte_carlo_resilience_engine import (
    MonteCarloResilienceEngine,
    get_default_monte_carlo_resilience_report,
    run_dual_parity_monte_carlo,
)
from engine.execution.nexus import NexusNode
from engine.workers.market_scanner import MarketScanner

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
REPORT_PATH = os.path.join(ROOT_DIR, "engine", "backtest", "reports", "chronological_backtest_report.json")
ACTIONS_PATH = os.path.join(ROOT_DIR, "src", "features", "backtest-metrics", "actions.ts")


def test_ssot_live_modules_parity():
    """MarketScanner y NexusNode deben consumir exactamente las reglas de strategy_ssot."""
    assert MarketScanner.APPROVED_SCALP_15M_EXECUTION == set(APPROVED_SCALP_15M_EXECUTION)
    assert MarketScanner.APPROVED_SWING_1H_EXECUTION == set(APPROVED_SWING_1H_EXECUTION)
    assert MarketScanner.SHORT_ONLY_ASYMMETRIC_ASSETS_SOP137 == set(SHORT_ONLY_ASYMMETRIC_ASSETS_SOP137)
    assert MarketScanner.LONG_ONLY_STRUCTURAL_ASSETS_SOP137 == set(LONG_ONLY_STRUCTURAL_ASSETS_SOP137)
    assert MarketScanner.TOXIC_UTC_HOURS_SOP137 == set(TOXIC_UTC_HOURS_SOP137)
    assert NexusNode.MAX_UNPROTECTED_RISK_POSITIONS == BASE_MAX_UNPROTECTED_RISK_SLOTS

    for sym in ("BTCUSDT", "ETHUSDT", "XAUUSDT", "XRPUSDT", "LINKUSDT", "SUIUSDT", "AVAXUSDT"):
        for tf in ("15m", "1h"):
            assert MarketScanner.is_quant_approved_pair(sym, tf) == is_quant_approved_pair(sym, tf)
        for direction in ("LONG", "SHORT"):
            assert MarketScanner.is_directional_setup_allowed_sop137(sym, direction) == is_directional_setup_allowed_sop137(sym, direction)
        assert NexusNode.calculate_priority_score({"symbol": sym, "confluence_score": 80.0}) == calculate_priority_score(sym, 80.0)

    for hr in range(24):
        dt = datetime(2026, 6, 1, hr, 0, tzinfo=timezone.utc)
        assert MarketScanner.is_toxic_hour_sop137(dt) == (hr in TOXIC_UTC_HOURS_SOP137)


def test_chronological_report_obeys_all_live_gates():
    """Todo trade del reporte cronológico debe cumplir 1:1 las compuertas de producción."""
    assert os.path.exists(REPORT_PATH)
    with open(REPORT_PATH, "r", encoding="utf-8") as f:
        report = json.load(f)

    assert report["advanced_protocols"]["quant_pair_gate_sop139"] is True
    assert report["advanced_protocols"]["directional_guard_sop137"] is True

    for tr in report["trades"]:
        sym = tr["symbol"]
        tf = tr.get("interval", "15m")
        direction = tr["direction"]
        entry_hour = datetime.fromisoformat(str(tr["entry_time"]).replace("Z", "+00:00")).hour

        assert sym not in PRUNED_NEGATIVE_EXPECTANCY_ASSETS, f"Activo podado {sym} apareció en reporte"
        assert is_quant_approved_pair(sym, tf), f"Par bloqueado {sym}:{tf} apareció en reporte"
        assert is_directional_setup_allowed_sop137(sym, direction), f"Dirección vetada {sym} {direction} en reporte"
        assert entry_hour not in TOXIC_UTC_HOURS_SOP137, f"Hora tóxica {entry_hour}h UTC en reporte"


def test_dual_monte_carlo_parity_and_tier1_solvency():
    """Monte Carlo debe alimentarse del reporte cronológico y superar TIER_1_AAA con fricción SOP-119."""
    with open(REPORT_PATH, "r", encoding="utf-8") as f:
        report = json.load(f)

    mc_parity = report.get("monte_carlo_parity")
    assert mc_parity is not None, "chronological_backtest_report.json debe incluir monte_carlo_parity"
    assert mc_parity["sampleSize"] == report["institutional_mode"]["total_trades"]

    for mode in ("theoretical", "realisticSop119"):
        m = mc_parity[mode]
        assert m["solvencyGrade"] == "TIER_1_AAA", f"{mode} no alcanzó TIER_1_AAA"
        assert m["probabilityOfProfitPct"] >= 90.0
        assert m["riskOfRuinPct"] <= 2.5

    default_mc = get_default_monte_carlo_resilience_report(apply_live_friction=False)
    assert default_mc["sourceMode"] == "CHRONOLOGICAL_REPORT_SSOT"
    assert default_mc["medianFinalNetR"] == mc_parity["theoretical"]["medianFinalNetR"]

    dual_recheck = run_dual_parity_monte_carlo(REPORT_PATH)
    assert dual_recheck["realisticSop119"]["medianFinalNetR"] == mc_parity["realisticSop119"]["medianFinalNetR"]


def test_ui_actions_matches_chronological_report_ssot():
    """Los KPIs servidos por src/features/backtest-metrics/actions.ts deben coincidir 1:1 con el reporte JSON."""
    with open(REPORT_PATH, "r", encoding="utf-8") as f:
        report = json.load(f)
    with open(ACTIONS_PATH, "r", encoding="utf-8") as f:
        actions_src = f.read()

    inst = report["institutional_mode"]
    comp = report["compounding_mode"]

    expected_fields = {
        "totalTrades": str(inst["total_trades"]),
        "profitFactorBase": str(inst["profit_factor_base"]),
        "profitFactorAlphaTier": str(inst["profit_factor_alpha"]),
        "totalNetRBase": str(inst["total_r_base"]),
        "totalNetRAlphaTier": str(inst["total_r_alpha"]),
        "maxDrawdownBasePct": str(inst["max_drawdown_base_pct"]),
        "maxDrawdownAlphaTierPct": str(inst["max_drawdown_alpha_pct"]),
        "compoundedCapitalFinal": str(comp["final_usd"]),
    }

    for field_name, expected_val in expected_fields.items():
        match = re.search(rf"{field_name}:\s*([-0-9.]+)", actions_src)
        assert match is not None, f"Campo {field_name} no encontrado en actions.ts"
        ui_val = float(match.group(1))
        rep_val = float(expected_val)
        if "Drawdown" in field_name:
            ui_val = abs(ui_val)
            rep_val = abs(rep_val)
        assert ui_val == pytest.approx(rep_val, rel=1e-4), (
            f"Desfase SSoT en {field_name}: UI={match.group(1)} vs Reporte={expected_val}"
        )
