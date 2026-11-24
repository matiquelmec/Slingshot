"""
engine/tests/test_sop147_runtime_audit_fixes.py
Tests de regresión y contratos arquitectónicos SOP-147:
1. Aislamiento AST permanente: engine/aiq/ y engine/agents/ jamás importan engine/execution/.
2. Conteo exacto de riesgo por positionId en modo Isolated-Multi (get_unprotected_risk_count).
3. Extracción segura de símbolo en claves Isolated-Multi (_extract_symbol_from_entry).
4. Congelamiento de mutadores adaptativos en ConfluenceManager (FORWARD_TEST_FROZEN_MODE).
5. Propagación de is_btc_blocked e is_avwap_blocked en MarketScanner._format_opportunity().
"""

import ast
from pathlib import Path
import pandas as pd

from engine.core.confluence import _resolve_factor_weight, confluence_manager
from engine.core.strategy_ssot import (
    ENABLE_AUTONOMOUS_GITOPS_POLL,
    ENABLE_FAST_VELOCITY_ESCAPE,
    FORWARD_TEST_FROZEN_MODE,
)
from engine.execution.nexus import NexusNode, _extract_symbol_from_entry
from engine.workers.market_scanner import MarketScanner


def test_ai_and_agents_never_import_execution_modules():
    """Garantía AST permanente: ningún módulo en engine/aiq/ o engine/agents/ importa engine/execution/."""
    root = Path(__file__).resolve().parent.parent
    forbidden_fragments = ("engine.execution", "bitunix_executor", "mt5_bridge")
    violations = []

    for subdir in ("aiq", "agents"):
        target_dir = root / subdir
        if not target_dir.exists():
            continue
        for py_file in target_dir.rglob("*.py"):
            tree = ast.parse(py_file.read_text(encoding="utf-8", errors="ignore"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if any(f in alias.name for f in forbidden_fragments):
                            violations.append(f"{py_file.name}: import {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    if any(f in mod for f in forbidden_fragments):
                        violations.append(f"{py_file.name}: from {mod} import ...")

    assert violations == [], f"Violación de aislamiento IA -> Ejecución: {violations}"


def test_sop147_default_governance_flags():
    assert FORWARD_TEST_FROZEN_MODE is True
    assert ENABLE_FAST_VELOCITY_ESCAPE is False
    assert ENABLE_AUTONOMOUS_GITOPS_POLL is False


def test_extract_symbol_from_isolated_multi_key():
    assert _extract_symbol_from_entry("primary_XRPUSDT_192837465") == "XRPUSDT"
    assert _extract_symbol_from_entry("primary_TIAUSDT") == "TIAUSDT"
    assert _extract_symbol_from_entry("SOLUSDT") == "SOLUSDT"


def test_unprotected_risk_count_isolated_multi_vs_legacy():
    node = NexusNode(dry_run=True)
    # 2 posiciones distintas en XRPUSDT (Isolated-Multi con positionId distinto) deben contar como 2
    node._active_positions = {
        "primary_XRPUSDT_1001": {
            "account_id": "primary",
            "signal": {"asset": "XRPUSDT", "type": "LONG", "price": 1.0, "stop_loss": 0.95},
            "execution": {"main_order_id": "1001"},
        },
        "primary_XRPUSDT_1002": {
            "account_id": "primary",
            "signal": {"asset": "XRPUSDT", "type": "LONG", "price": 1.01, "stop_loss": 0.96},
            "execution": {"main_order_id": "1002"},
        },
    }
    assert node.get_unprotected_risk_count("primary") == 2

    # Entradas legacy duplicadas sin positionId ('SOLUSDT' + 'primary_SOLUSDT') siguen contando como 1
    node._active_positions = {
        "SOLUSDT": {
            "account_id": "primary",
            "signal": {"asset": "SOLUSDT", "type": "LONG", "price": 180.0, "stop_loss": 175.0},
        },
        "primary_SOLUSDT": {
            "account_id": "primary",
            "signal": {"asset": "SOLUSDT", "type": "LONG", "price": 180.0, "stop_loss": 175.0},
        },
    }
    assert node.get_unprotected_risk_count("primary") == 1


def test_frozen_forward_test_weights_and_format_opportunity_guards():
    assert _resolve_factor_weight("poi_weight", default=40.0) == 40.0

    scanner = MarketScanner()
    # BTC bajista bajo EMA200 -> señal LONG en altcoin debe marcar is_btc_blocked=True
    btc_prices = [100000.0] * 199 + [90000.0]
    btc_df = pd.DataFrame({"close": btc_prices})
    alt_df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-11-20", periods=30, freq="15min", tz="UTC"),
            "open": [10.0] * 30,
            "high": [10.2] * 30,
            "low": [9.8] * 30,
            "close": [10.0] * 30,
            "volume": [1000.0] * 30,
        }
    )
    sig = {
        "asset": "NEARUSDT",
        "signal_type": "LONG",
        "price": 10.0,
        "stop_loss": 9.8,
        "tp1": 10.25,
        "tp2": 10.4,
        "take_profit_3r": 10.7,
        "confluence": {"score": 80, "checklist": [], "asset_health": {"ker": 0.45}},
    }
    opp = scanner._format_opportunity(sig, is_active=True, df=alt_df, interval="15m", btc_df=btc_df)
    assert opp["btc_aligned"] is False
    assert opp["is_btc_blocked"] is True
    assert "is_avwap_blocked" in opp
