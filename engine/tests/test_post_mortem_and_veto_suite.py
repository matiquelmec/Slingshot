"""
engine/tests/test_post_mortem_and_veto_suite.py
===============================================
Suite de pruebas para el Agente Post-Mortem y el Sistema de Vetos
Tácticos con NVIDIA NIM (SOP-76 / Slingshot v53.0).
"""

import time
import pytest
import asyncio
from pathlib import Path
from engine.core.vault import SlingshotVault
from engine.agents.post_mortem_agent import PostMortemAgent


@pytest.fixture
def temp_vault(tmp_path):
    """Instancia limpia de SlingshotVault en SQLite temporal."""
    db_file = tmp_path / "test_pm_vault.db"
    return SlingshotVault(db_path=db_file)


def test_post_mortem_veto_lifecycle(temp_vault):
    """Verifica el ciclo de vida del veto: inserción, consulta y expiración."""
    symbol = "SOLUSDT"

    # Inicialmente no debe estar vetado
    vetoed, reason = temp_vault.is_symbol_vetoed(symbol)
    assert vetoed is False
    assert reason is None

    # Registrar veto de 2 segundos
    temp_vault.add_post_mortem_veto(
        symbol=symbol,
        condition_tag="LIQUIDITY_SWEEP",
        reason="Veto por barrido institucional de stops",
        duration_seconds=2
    )

    # Ahora debe figurar como vetado
    vetoed, reason = temp_vault.is_symbol_vetoed(symbol)
    assert vetoed is True
    assert "barrido institucional" in reason

    # Esperar expiración
    time.sleep(2.5)
    vetoed_after, _ = temp_vault.is_symbol_vetoed(symbol)
    assert vetoed_after is False


def test_post_mortem_report_recording(temp_vault):
    """Verifica que los reportes de análisis causal se persisten correctamente."""
    temp_vault.record_post_mortem_report(
        trade_id="trade_101",
        symbol="BTCUSDT",
        side="LONG",
        pnl_usd=-45.5,
        loss_category="FALSE_BREAKOUT_CHOP",
        causal_analysis="Falso quiebre en resistencia 15m sin volumen de absorción.",
        preventive_rule="Exigir confirmación de vela con volumen > 1.5x antes de entrar."
    )

    with temp_vault._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT loss_category, pnl_usd, preventive_rule FROM post_mortem_reports WHERE trade_id = 'trade_101'")
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "FALSE_BREAKOUT_CHOP"
        assert row[1] == -45.5
        assert "volumen > 1.5x" in row[2]


@pytest.mark.asyncio
async def test_post_mortem_agent_deterministic_fallback():
    """Verifica que el agente genera un diagnóstico coherente aun sin conexión a NVIDIA NIM."""
    agent = PostMortemAgent()
    report = await agent.analyze_closed_loss_trade(
        trade_id="test_loss_99",
        symbol="ETHUSDT",
        side="BUY",
        entry_price=2500.0,
        exit_price=2480.0,
        pnl_r=-1.0,
        pnl_usd=-20.0,
        exit_reason="SL",
        context_data={"regime": "CHOPPY", "rvol": 2.2, "session": "ASIA"}
    )

    assert isinstance(report, dict)
    assert "loss_category" in report
    assert "causal_analysis" in report
    assert "preventive_rule" in report
    assert "apply_veto" in report
    assert isinstance(report["apply_veto"], bool)
