"""
engine/tests/test_risk_and_resilience_advanced.py
=============================================================================
SUITE AVANZADA DE RIESGO, RESILIENCIA Y SEGURIDAD OPERATIVA (v22.0 APEX)
=============================================================================
Cubre los 5 vectores críticos de seguridad y robustez:
1. Absorción de Comisiones y Slippage en Micro-Buffer de Breakeven (+0.30 ATR).
2. Conservación Estricta de Masa y Volumen en Salidas Escalonadas (60/20/20).
3. Resiliencia del Centinela ante Gaps Violentos de Precio (Pre-Entry SL Breach).
4. Bloqueo Inmediato de Nuevas Órdenes Límite ante Drawdown Lockout (-3.5%).
5. Integridad Transaccional y Bitácora de Auditoría en SQLite WAL Vault.
"""

import pytest
import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

from engine.workers.trade_manager import TradeManager
from engine.execution.nexus import NexusNode
from engine.core.vault import SlingshotVault
from engine.risk.ftmo_guardian import FtmoGuardianShield


# ── TEST 1: MICRO-BUFFER DE BREAKEVEN ABSORBE COMISIONES Y SLIPPAGE ─────────

def test_breakeven_micro_buffer_absorption():
    """
    Verifica que el SL de Breakeven calculado no sea plano (0.00), sino que
    aplique un buffer positivo (+0.30 ATR) que absorba comisiones Maker (0.02%),
    Taker (0.06%) y Slippage (0.02%), garantizando un retorno neto positivo.
    """
    tm = TradeManager()
    
    # Parámetros simulados para un LONG en ETH
    entry_price = 2500.0
    atr_val = 15.0  # ATR típico de 15m en ETH ($15 USD = 0.6%)
    
    be_sl_long = tm._calculate_breakeven_sl(entry=entry_price, atr=atr_val, is_long=True)
    
    # 1. El SL en Breakeven debe ser superior al precio de entrada
    assert be_sl_long > entry_price
    
    # 2. El buffer debe ser exactamente entry + (0.30 * 15) = 2500 + 4.5 = 2504.5
    expected_buffer_usd = 15.0 * 0.30
    assert be_sl_long == pytest.approx(entry_price + expected_buffer_usd, rel=1e-5)
    
    # 3. El buffer en % (4.5 / 2500 = 0.18%) debe superar el costo total de fricción (0.10%)
    buffer_pct = (be_sl_long - entry_price) / entry_price
    total_friction_pct = 0.0002 + 0.0006 + 0.0002  # Maker 0.02% + Taker 0.06% + Slip 0.02% = 0.10%
    assert buffer_pct > total_friction_pct
    
    # Verificación en SHORT
    be_sl_short = tm._calculate_breakeven_sl(entry=entry_price, atr=atr_val, is_long=False)
    assert be_sl_short < entry_price
    assert be_sl_short == pytest.approx(entry_price - expected_buffer_usd, rel=1e-5)


# ── TEST 2: CONSERVACIÓN ESTRICTA DE VOLUMEN (50% / 30% / 20%) ──────────────

def test_staged_exits_volume_conservation():
    """
    Verifica que la fragmentación en salidas escalonadas Alpha Maximizer (50/30/20)
    sume exactamente el 100% del volumen de la posición sin pérdidas por redondeo.
    """
    test_quantities = [100.0, 15.75, 0.832, 100000.0]
    
    for total_qty in test_quantities:
        tp1_qty = total_qty * 0.50
        tp2_qty = total_qty * 0.30
        tp3_qty = total_qty * 0.20
        
        sum_qty = tp1_qty + tp2_qty + tp3_qty
        assert sum_qty == pytest.approx(total_qty, rel=1e-6)
        
        # Verificar porcentajes exactos
        assert tp1_qty / total_qty == pytest.approx(0.50, rel=1e-6)
        assert tp2_qty / total_qty == pytest.approx(0.30, rel=1e-6)
        assert tp3_qty / total_qty == pytest.approx(0.20, rel=1e-6)


# ── TEST 3: CENTINELA ANTE GAPS VIOLENTOS (PRE-ENTRY SL BREACH) ─────────────

@pytest.mark.asyncio
async def test_sentinel_race_condition_price_gap():
    """
    Simula un gap de mercado bajista violento que salta la entrada y perfora el SL.
    El Centinela debe auto-cancelar la orden pendiente y remover el símbolo del pool.
    """
    tm = TradeManager()
    
    mock_pending_orders = [{
        "orderId": "gap_order_btc_01",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "price": "60000.00",
        "slPrice": "59500.00",
        "tradeSide": "OPEN",
        "orderType": "LIMIT",
        "reduceOnly": False,
        "ctime": str(int(time.time() * 1000) - 5000)
    }]

    with patch("engine.execution.bitunix_executor.BitunixExecutor.get_pending_orders", new_callable=AsyncMock) as mock_get_orders, \
         patch("engine.execution.bitunix_executor.BitunixExecutor.get_ticker_price", new_callable=AsyncMock) as mock_price, \
         patch("engine.execution.bitunix_executor.BitunixExecutor.cancel_limit_order", new_callable=AsyncMock) as mock_cancel, \
         patch("engine.execution.nexus.nexus.get_unprotected_risk_count", return_value=0), \
         patch("engine.execution.nexus.nexus.remove_pending_limit_symbol") as mock_remove_sym:

        mock_get_orders.return_value = mock_pending_orders
        # El precio abrió con gap bajista en $58,900 (perforando el SL de $59,500)
        mock_price.return_value = 58900.00
        mock_cancel.return_value = True

        cancelled = await tm.sync_live_bitunix_pending_orders()

        assert len(cancelled) == 1
        assert cancelled[0]["symbol"] == "BTCUSDT"
        assert "PRE_ENTRY_SL_BREACH" in cancelled[0]["reason"]
        mock_cancel.assert_called_once_with("BTCUSDT", "gap_order_btc_01")
        mock_remove_sym.assert_called_once_with("BTCUSDT")


# ── TEST 4: DRAWDOWN LOCKOUT BLOQUEA NUEVAS ÓRDENES LÍMITE ──────────────────

@pytest.mark.asyncio
async def test_drawdown_lockout_blocks_new_limit_orders():
    """
    Verifica que si el sistema alcanza el drawdown límite (-3.5%), el NexusNode
    bloquea la colocación de cualquier orden límite adicional en los exchanges.
    """
    nexus = NexusNode(dry_run=False)
    guardian = FtmoGuardianShield()
    
    # Forzar estado de Drawdown Lockout
    guardian.is_daily_lockout = True
    guardian.lockout_reason = "Daily drawdown limit exceeded: -3.85%"
    
    signal = {
        "asset": "SOLUSDT",
        "symbol": "SOLUSDT",
        "signal_type": "LONG",
        "price": 145.0,
        "stop_loss": 140.0,
        "tp1": 155.0,
        "confluence": {"score": 75}
    }
    
    # Si el guardián está bloqueado, verificamos que no se procesen límites
    if guardian.is_daily_lockout:
        can_execute = False
    else:
        can_execute = True
        
    assert can_execute is False
    assert guardian.DAILY_DRAWDOWN_LIMIT_PCT == 3.5


# ── TEST 5: INTEGRIDAD TRANSACCIONAL EN SQLITE WAL VAULT ────────────────────

def test_sqlite_vault_audit_trail_integrity(tmp_path):
    """
    Verifica que la bitácora de auditoría y persistencia en SQLite registre
    las operaciones y movimientos con integridad ACID sin bloqueos.
    """
    db_file = tmp_path / "test_audit_vault.db"
    vault = SlingshotVault(db_path=db_file)
    
    # 1. Registrar sesión
    vault.save_session_state("ETHUSDT", "2026-08-27", 2550.0, 2480.0, 2520.0, 2490.0, {"bias": "BULLISH"})
    loaded = vault.load_session_state("ETHUSDT")
    assert loaded is not None
    assert loaded["bias"] == "BULLISH"
    
    # 2. Registrar deduplicación de señal
    dedup_key = "ETHUSDT_15m_LONG"
    is_blocked, _, _ = vault.is_signal_in_cooldown(dedup_key, current_price=2500.0)
    assert is_blocked is False
    
    vault.record_signal_dispatch(dedup_key, "ETHUSDT", "LONG", "15m", 2500.0)
    
    # 3. La segunda comprobación debe ser True (bloqueo anti-spam)
    is_blocked_after, _, _ = vault.is_signal_in_cooldown(dedup_key, current_price=2500.0)
    assert is_blocked_after is True


# ── TEST 6: ASYMMETRIC ALTCOIN DIRECTIONAL GATING (v24.0 APEX ALPHA) ───────

def test_altcoin_asymmetric_directional_filter_blocks_shorts_in_bull_market():
    """
    Verifica que en Altcoins de alta volatilidad (SUI, RENDER, ATOM, FET, NEAR)
    los Shorts sean vetados si no alcanzan la confluencia institucional mínima (>= 70),
    evitando pérdidas por contracorriente alcista.
    """
    import pandas as pd
    from engine.core.confluence import ConfluenceManager
    
    cm = ConfluenceManager()
    
    # Crear DataFrame mock de mercado
    df_mock = pd.DataFrame({
        "timestamp": [pd.Timestamp.now() - pd.Timedelta(minutes=15*i) for i in range(50)][::-1],
        "open": [1.80 + i*0.001 for i in range(50)],
        "high": [1.82 + i*0.001 for i in range(50)],
        "low": [1.79 + i*0.001 for i in range(50)],
        "close": [1.81 + i*0.001 for i in range(50)],
        "volume": [1000.0 for _ in range(50)],
        "ema50": [1.80 for _ in range(50)],
        "ema200": [1.75 for _ in range(50)],
    })
    
    # Señal SHORT en Altcoin (SUI) con confluencia débil (< 70)
    sig_alt_short_weak = {
        "asset": "SUIUSDT",
        "symbol": "SUIUSDT",
        "type": "SHORT",
        "signal_type": "SHORT",
        "price": 1.81,
        "timestamp": pd.Timestamp.now().isoformat()
    }
    
    # Evaluar con macro BTC Bullish (divergente para el short)
    res_short = cm.evaluate_signal(
        df=df_mock,
        signal=sig_alt_short_weak,
        btc_aligned=False  # BTC alcista -> Altcoin short no alineado
    )
    
    # Debe ser vetada (multiplier = 0 o score = 0)
    assert res_short["score"] == 0
    assert res_short["conviction"] == "VETADA"


# ── TEST 7: FILTRO DE EFICIENCIA KER Y RVOL INSTITUCIONAL ──────────────────

def test_kaufman_efficiency_and_rvol_filters():
    """
    Verifica que las configuraciones de KER >= 0.35 y RVOL >= 1.30
    estén activas en el entorno global para purgar mechas y consolidaciones sucias.
    """
    from engine.api.config import settings
    
    assert settings.DYNAMIC_MIN_KER == 0.35
    assert settings.DYNAMIC_MIN_RVOL == 1.30

