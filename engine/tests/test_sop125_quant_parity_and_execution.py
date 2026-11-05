"""
engine/tests/test_sop125_quant_parity_and_execution.py
=============================================================================
SUITE DE CERTIFICACIÓN CUANTITATIVA SOP-125:
1. Matriz de Selección Estricta por Backtest (437 trades) + Monte Carlo (5,000 rutas).
2. Erradicación del Bug de Breakeven Prematuro al +1.0% (+0.55R) en TradeManager.
3. Healthcheck O(1) No Bloqueante (get_cached_ollama_status < 5ms).
4. Tope Duro de Riesgo por Operación (<= 3.50%) en RiskManager.
5. Guardián Anti-Polvo Multi-Cuenta (avail_margin < $5.00 USDT) en NexusNode.
=============================================================================
"""

import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from engine.workers.market_scanner import MarketScanner
from engine.workers.trade_manager import TradeManager
from engine.risk.risk_manager import RiskManager
from engine.execution.nexus import NexusNode
from engine.api.advisor import get_cached_ollama_status


def test_sop125_quant_approved_pair_matrix():
    """
    Certifica que únicamente los 11 pares Activo:Timeframe aprobados por Backtest
    (PF >= 1.50, Exp >= +0.17R) y Monte Carlo (5,000 rutas, Win% >= 80%) pasen el filtro.
    """
    approved_15m = ["BNBUSDT", "ETHUSDT", "SOLUSDT", "NEARUSDT", "FETUSDT", "INJUSDT", "ATOMUSDT"]
    for sym in approved_15m:
        assert MarketScanner.is_quant_approved_pair(sym, "15m") is True, f"{sym}:15m debe estar aprobado"

    approved_1h = ["XAUUSDT", "BTCUSDT", "NEARUSDT", "ATOMUSDT"]
    for sym in approved_1h:
        assert MarketScanner.is_quant_approved_pair(sym, "1h") is True, f"{sym}:1h debe estar aprobado"

    # Pares matemáticamente rechazados por Backtest y Monte Carlo
    rejected_pairs = [
        ("INJUSDT", "1h"),   # PF 0.80, Exp -0.096R, MC 32.4%
        ("SUIUSDT", "15m"),  # PF 1.16, Exp +0.058R, MC 62.5%
        ("LINKUSDT", "15m"), # PF 1.16, Exp +0.064R, MC 61.1%
        ("LINKUSDT", "1h"),  # PF 1.41, Exp +0.145R, MC 72.2%
        ("BTCUSDT", "15m"),  # PF 1.10, MaxDD 8.10R, MC 61.3%
        ("ETHUSDT", "1h"),   # WR 36.4%, MC 69.7%
        ("SOLUSDT", "1h"),   # WR 35.7%, MC 73.5%
        ("TIAUSDT", "15m"),  # 0 setups / Quarantined
    ]
    for sym, tf in rejected_pairs:
        assert MarketScanner.is_quant_approved_pair(sym, tf) is False, f"{sym}:{tf} debe estar rechazado"


@pytest.mark.asyncio
async def test_sop125_no_premature_breakeven_at_1_percent():
    """
    Certifica que TradeManager NO mueva el Stop Loss a Breakeven cuando el precio
    avanza apenas +1.0% (+0.55R en altcoins con SL de 1.80%), sino exclusivamente
    al alcanzar el umbral real en R (be_threshold >= 1.0R).
    """
    tm = TradeManager()
    assert tm.POLL_INTERVAL_SECONDS == 10

    # Caso 1: NEARUSDT LONG con Entrada=5.00, SL=4.91 (Riesgo 1R = 0.09 = 1.80%).
    # Precio actual = 5.05 (+1.0% sobre entrada, pero apenas +0.55R).
    # Antes del fix, cur_price > entry_price * 1.01 forzaba Fast BE prematuro en +0.55R.
    mock_pos_055r = [{
        "symbol": "NEARUSDT",
        "side": "BUY",
        "entryPrice": 5.00,
        "lastPrice": 5.05,  # +1.0% pero solo +0.555R (< 0.60R y < 1.0R)
        "slPrice": 4.91,
        "positionId": "pos_near_055r"
    }]

    with patch("engine.execution.account_manager.AccountManager.get_all_executors") as mock_execs:
        mock_bitunix = MagicMock()
        mock_bitunix.account_label = "PrimaryTest"
        mock_bitunix.get_pending_positions = AsyncMock(return_value=mock_pos_055r)
        mock_bitunix.get_pending_orders = AsyncMock(return_value=[])
        mock_bitunix._request = AsyncMock(return_value={"code": 0, "data": []})
        mock_bitunix.modify_position_tpsl = AsyncMock(return_value=True)
        mock_execs.return_value = {"primary": mock_bitunix}

        res_early = await tm.sync_live_bitunix_positions()
        assert len(res_early) == 1
        assert res_early[0]["r_profit"] == pytest.approx(0.56, abs=0.02)
        assert "FAST_BE" not in res_early[0]["status"]
        mock_bitunix.modify_position_tpsl.assert_not_awaited()


def test_sop125_non_blocking_health_ollama_cache():
    """Certifica que get_cached_ollama_status responda en < 5ms sin bloquear el event loop."""
    t0 = time.perf_counter()
    status = get_cached_ollama_status()
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    assert isinstance(status, bool)
    assert elapsed_ms < 5.0


def test_sop125_hard_risk_ceiling_in_dollar_sizing():
    """Certifica que calculate_dollar_risk_position limite el riesgo máximo a 3.50% por trade."""
    calc = RiskManager.calculate_dollar_risk_position(
        account_balance=500.0,
        risk_pct=0.10,  # Intento de arriesgar 10% ($50)
        entry_price=100.0,
        sl_price=98.0,
        leverage=10,
        qty_decimals=2
    )
    assert calc["approved"] is True
    # Techo duro de 3.50% de $500 = $17.50 USDT máximo
    assert calc["projected_loss"] <= 17.50


@pytest.mark.asyncio
async def test_sop125_dust_balance_guard_in_nexus():
    """
    Certifica que una cuenta secundaria con polvo residual (< $5.00 USDT, ej: 6.66e-9 USDT en cliente_2)
    sea omitida limpiamente y marque _last_verified_balance = 0.0.
    """
    nexus = NexusNode(dry_run=False)
    acc = MagicMock()
    acc.account_id = "cliente_2"
    acc.label = "Cliente 2 Dust"
    acc.is_primary = False
    acc.risk_pct = 0.025

    ex = MagicMock()
    ex.dry_run = False
    ex.account_label = "Cliente 2 Dust"
    ex.get_net_available_margin_usdt = AsyncMock(return_value=0.00000000666)
    ex.get_available_margin_usdt = AsyncMock(return_value=0.00000000666)
    ex.get_account_balance = AsyncMock(return_value=0.00000000666)
    ex.get_pending_positions = AsyncMock(return_value=[])
    ex.get_pending_orders = AsyncMock(return_value=[])
    ex.place_limit_signal = AsyncMock()

    sig = {
        "asset": "BNBUSDT",
        "symbol": "BNBUSDT",
        "direction": "LONG",
        "confluence_score": 80.0,
        "price": 600.0,
        "stop_loss": 590.0
    }
    res = await nexus._place_limit_for_account(ex, acc, sig, safe_lev=10, entry_p=600.0, sl_p=590.0)
    assert res is None
    assert ex._last_verified_balance == 0.0
    ex.place_limit_signal.assert_not_awaited()
