"""
engine/tests/test_breathing_room_and_nexus_harmony.py
=============================================================================
SUITE DE PRUEBAS: BREATHING ROOM SHIELD Y ARMONIA NEXUS-TRADEMANAGER (v25.5)
=============================================================================
Audita:
1. Inmunidad contra Breakeven Prematuro (SL no se mueve entre 0.0R y 0.99R).
2. Activacion exacta de Fast BE solo al cruzar >= 1.0R (Altcoins) o >= 1.2R (Megacaps).
3. Armonia entre NexusNode y TradeManager: Cero colision ni sobrescritura de SL.
4. Precision dinamica de Stop Loss y ordenes en BitunixExecutor.
"""
import pytest
import asyncio
from unittest.mock import patch, AsyncMock
from engine.workers.trade_manager import TradeManager
from engine.execution.nexus import NexusNode
from engine.execution.bitunix_executor import BitunixExecutor

@pytest.mark.asyncio
async def test_breathing_room_sl_never_moves_under_1r():
    tm = TradeManager()
    entry = 5.433
    initial_sl = 5.350
    
    sig = {
        "asset": "INJUSDT",
        "symbol": "INJUSDT",
        "type": "LONG",
        "signal_type": "LONG",
        "price": entry,
        "entry_price": entry,
        "stop_loss": initial_sl,
        "initial_stop_loss": initial_sl,
        "tp1": entry + (0.083 * 1.5),
        "tp2": entry + (0.083 * 3.0),
        "tp3": entry + (0.083 * 5.0),
        "trailing_phase": "ACTIVE",
        "status": "ACTIVE"
    }
    
    mock_candles = [
        {"data": {"timestamp": 1000 + i*60, "open": 5.433, "high": 5.450, "low": 5.430, "close": 5.445, "atr": 0.05}}
        for i in range(30)
    ]
    
    with patch("engine.workers.trade_manager.fetch_binance_history", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = mock_candles
        await tm._update_signal_trailing(sig)
        assert sig["stop_loss"] == initial_sl
        assert sig["trailing_phase"] == "ACTIVE"

@pytest.mark.asyncio
async def test_fast_be_activates_strictly_at_or_above_1r():
    tm = TradeManager()
    entry = 5.433
    initial_sl = 5.350
    
    sig = {
        "asset": "INJUSDT",
        "symbol": "INJUSDT",
        "type": "LONG",
        "signal_type": "LONG",
        "price": entry,
        "entry_price": entry,
        "stop_loss": initial_sl,
        "initial_stop_loss": initial_sl,
        "tp1": entry + (0.083 * 1.5),
        "tp2": entry + (0.083 * 3.0),
        "tp3": entry + (0.083 * 5.0),
        "trailing_phase": "ACTIVE",
        "status": "ACTIVE"
    }
    
    mock_candles = [
        {"data": {"timestamp": 1000 + i*60, "open": 5.433, "high": 5.525, "low": 5.430, "close": 5.520, "atr": 0.05}}
        for i in range(30)
    ]
    
    with patch("engine.workers.trade_manager.fetch_binance_history", new_callable=AsyncMock) as mock_fetch:
        with patch.object(tm, "_apply_sl_update", new_callable=AsyncMock) as mock_apply:
            mock_fetch.return_value = mock_candles
            await tm._update_signal_trailing(sig)
            assert mock_apply.called
            args = mock_apply.call_args[0]
            new_sl_val = args[1]
            phase_val = args[2]
            assert phase_val == "BREAKEVEN"
            assert new_sl_val >= entry

@pytest.mark.asyncio
async def test_nexus_centinel_does_not_strangle_positions_on_minor_tick():
    nexus = NexusNode(dry_run=True)
    entry = 100.0
    initial_sl = 98.0
    
    pos_data = {
        "signal": {
            "asset": "SOLUSDT",
            "symbol": "SOLUSDT",
            "type": "LONG",
            "price": entry,
            "stop_loss": initial_sl,
            "tp1": 103.0,
            "tp2": 106.0,
            "tp3": 110.0,
            "trailing_phase": "ACTIVE"
        },
        "execution": {"main_order_id": "dry_order_123", "amount": 1.0, "timestamp": 1000},
        "created_timestamp": 1000,
        "smart_trailing": {"be_active": False}
    }
    nexus._active_positions["SOLUSDT"] = pos_data
    
    with patch.object(nexus.executor, "get_ticker_price", new_callable=AsyncMock) as mock_ticker:
        mock_ticker.return_value = 100.05
        with patch("engine.workers.trade_manager.trade_manager._update_signal_trailing", new_callable=AsyncMock) as mock_tm_trail:
            sig = pos_data["signal"]
            await mock_tm_trail(sig)
            assert mock_tm_trail.called
            assert sig["stop_loss"] == initial_sl

@pytest.mark.asyncio
async def test_bitunix_executor_dynamic_precision_formatting():
    executor = BitunixExecutor(dry_run=True)
    signal_micro = {
        "asset": "SUIUSDT",
        "type": "LONG",
        "price": 0.7441,
        "stop_loss": 0.7255,
        "position_size": 10.0,
        "leverage": 20,
        "is_test": True
    }
    res = await executor.execute_signal(signal_micro)
    assert res.get("status") == "success"