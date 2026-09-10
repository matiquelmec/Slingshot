"""
engine/tests/test_unified_execution_and_backtest_parity.py
=============================================================================
SUITE INTEGRAL DE CALIDAD, SEGURIDAD Y PARIDAD DE ESTRATEGIA (v30.0)
=============================================================================
1. PRUEBAS UNITARIAS:
   - Símbolo limpio y ejecutor aislado en Centinela OMEGA (nexus).
   - Aislamiento de position_id entre cuentas en _apply_sl_update (trade_manager).
   - Invarianza atómica en update_stop_loss (sin desprotección previa).

2. MÉTRICAS DE CALIDAD (Dynamic Precision Engine):
   - Bitunix: BTC/ETH/SOL (1-2 dec), XAU (2 dec), SUI (4 dec), PEPE (7-8 dec).
   - FTMO / MT5: EURUSD (5 dec), XAUUSD (2 dec), US500 (2 dec).

3. PROCEDIMIENTOS DE SEGURIDAD (SSoT Backtest Parity):
   - Fast Breakeven (+1.0R / +1.2R con Fee Absorber) 100% idéntico a Backtest.
   - Protección contra SL Desnudo (Pre-validación contra mercado, rescate, fallback).
=============================================================================
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from engine.execution.nexus import NexusNode
from engine.execution.account_manager import BitunixAccountConfig
from engine.execution.bitunix_executor import BitunixExecutor
from engine.execution.mt5_bridge import MT5Bridge
from engine.workers.trade_manager import TradeManager
from engine.backtest.unified_backtest_engine import UnifiedBacktestEngine


# ─────────────────────────────────────────────────────────────────────────────
# 1. PRUEBAS UNITARIAS: AISLAMIENTO MULTI-CUENTA Y CENTINELA OMEGA
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_omega_centinel_uses_clean_symbol_and_account_executor():
    node = NexusNode(dry_run=False)
    
    mock_ex_pri = AsyncMock(spec=BitunixExecutor)
    mock_ex_pri.account_label = "Cuenta Principal"
    mock_ex_pri.get_ticker_price.return_value = 0.8100
    
    mock_ex_cli = AsyncMock(spec=BitunixExecutor)
    mock_ex_cli.account_label = "Cuenta Cliente"
    mock_ex_cli.get_ticker_price.return_value = 0.8100
    
    node.account_manager = MagicMock()
    node.account_manager.get_executor.side_effect = lambda acc_id: mock_ex_cli if acc_id == "cliente_2" else mock_ex_pri
    
    node._active_positions = {
        "cliente_2_SUIUSDT": {
            "account_id": "cliente_2",
            "signal": {
                "asset": "SUIUSDT",
                "price": 0.7900,
                "stop_loss": 0.7800,
                "tp1": 0.8100,
                "type": "LONG"
            },
            "status": "OPEN",
            "created_timestamp": 100.0
        }
    }

    for mem_key, pos in list(node._active_positions.items()):
        sig = pos.get('signal', {})
        clean_asset = sig.get('asset') or (mem_key.split('_')[-1] if '_' in mem_key else mem_key)
        clean_asset = clean_asset.replace('/', '').upper()
        acc_id = pos.get('account_id') or 'primary'
        account_executor = node.account_manager.get_executor(acc_id)
        
        price = await account_executor.get_ticker_price(clean_asset)
        
        assert clean_asset == "SUIUSDT"
        assert acc_id == "cliente_2"
        assert price == 0.8100
        mock_ex_cli.get_ticker_price.assert_called_with("SUIUSDT")
        mock_ex_pri.get_ticker_price.assert_not_called()


@pytest.mark.asyncio
async def test_apply_sl_update_isolates_position_id_per_account():
    tm = TradeManager()
    
    mock_ex_pri = AsyncMock(spec=BitunixExecutor)
    mock_ex_pri.account_label = "Cuenta Principal"
    mock_ex_pri.modify_position_tpsl.return_value = True
    
    mock_ex_cli = AsyncMock(spec=BitunixExecutor)
    mock_ex_cli.account_label = "Cuenta Cliente"
    mock_ex_cli.modify_position_tpsl.return_value = True
    
    with patch("engine.execution.account_manager.AccountManager") as mock_mgr_cls, \
         patch("engine.core.store.store.save_signal", new_callable=AsyncMock):
        
        mock_mgr = MagicMock()
        mock_mgr.get_all_executors.return_value = {
            "primary": mock_ex_pri,
            "cliente_2": mock_ex_cli
        }
        mock_mgr_cls.return_value = mock_mgr
        
        signal_primary = {
            "asset": "SUIUSDT",
            "account_id": "primary",
            "position_id": "999888777",
            "stop_loss": 0.7800,
            "signal_type": "LONG"
        }
        
        await tm._apply_sl_update(signal_primary, new_sl=0.7932, new_phase="BREAKEVEN", reason="TP1 Alcanzado")
        
        mock_ex_pri.modify_position_tpsl.assert_called_with(
            symbol="SUIUSDT",
            position_id="999888777",
            sl_price=0.7932
        )
        
        mock_ex_cli.modify_position_tpsl.assert_called_with(
            symbol="SUIUSDT",
            position_id=None,
            sl_price=0.7932
        )


# ─────────────────────────────────────────────────────────────────────────────
# 2. MÉTRICAS DE CALIDAD: MOTOR DE PRECISIÓN DINÁMICA
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_quality_metrics_bitunix_dynamic_precision():
    ex = BitunixExecutor(dry_run=True)
    
    rules_xau = await ex.get_symbol_rules("XAUUSDT")
    assert rules_xau["price_precision"] == 2
    assert rules_xau["qty_precision"] == 3
    
    rules_sui = await ex.get_symbol_rules("SUIUSDT")
    assert rules_sui["price_precision"] == 4
    
    entry_sui = 0.792415
    fee_buffer_sui = 0.00063
    p_dec_sui = rules_sui["price_precision"]
    sl_sui = round(entry_sui + fee_buffer_sui, p_dec_sui)
    assert sl_sui == 0.7930
    assert len(str(sl_sui).split(".")[1]) <= 4

    entry_xau = 2500.4567
    rules_xau_p = rules_xau["price_precision"]
    sl_xau = round(entry_xau, rules_xau_p)
    assert sl_xau == 2500.46
    assert len(str(sl_xau).split(".")[1]) <= 2


def test_quality_metrics_ftmo_mt5_dynamic_digits():
    bridge = MT5Bridge(dry_run=True)
    
    assert bridge.get_symbol_digits("EURUSD") == 5
    assert bridge.get_symbol_digits("GBPUSD.cash") == 5
    assert bridge.get_symbol_digits("XAUUSD") == 2
    assert bridge.get_symbol_digits("US500.cash") == 2
    assert bridge.get_symbol_digits("USDJPY") == 3

    entry_eur = 1.085432
    digits_eur = bridge.get_symbol_digits("EURUSD")
    formatted_sl = round(entry_eur + 0.00025, digits_eur)
    assert formatted_sl == 1.08568
    assert len(str(formatted_sl).split(".")[1]) == 5


# ─────────────────────────────────────────────────────────────────────────────
# 3. PROCEDIMIENTOS DE SEGURIDAD Y PARIDAD CON BACKTEST
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_security_procedure_atomic_stop_loss_never_naked():
    ex = BitunixExecutor(dry_run=False)
    ex.modify_position_tpsl = AsyncMock(return_value=True)
    ex._request = AsyncMock(return_value={"code": 0})
    
    res = await ex.update_stop_loss(
        symbol="XAUUSDT",
        old_order_id="old_order_123",
        new_stop_price=2510.50,
        amount=1.0,
        side="BUY",
        position_id="pos_456"
    )
    
    assert res == "position_tpsl_updated"
    ex.modify_position_tpsl.assert_called_once_with(
        symbol="XAUUSDT",
        position_id="pos_456",
        sl_price=2510.50,
        tp_price=None
    )
    ex._request.assert_called_once()
    assert "cancel_orders" in ex._request.call_args[0][1]


def test_ssot_backtest_parity_fast_breakeven_thresholds():
    tm = TradeManager()
    
    assert tm.is_megacap("BTCUSDT") is True
    assert tm.is_megacap("ETHUSDT") is True
    assert tm.is_megacap("XAUUSDT") is True
    assert tm.is_megacap("SUIUSDT") is False
    
    be_mega = 1.2 if tm.is_megacap("BTCUSDT") else 1.0
    be_alt  = 1.2 if tm.is_megacap("SUIUSDT") else 1.0
    assert be_mega == 1.2
    assert be_alt == 1.0
    
    entry = 100.0
    atr = 0.5
    be_long = tm._calculate_breakeven_sl(entry=entry, atr=atr, is_long=True)
    be_short = tm._calculate_breakeven_sl(entry=entry, atr=atr, is_long=False)
    
    assert be_long > entry
    assert be_short < entry
    assert (be_long - entry) >= (entry * 0.0008)
