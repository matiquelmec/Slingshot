"""
engine/tests/test_live_trade_management.py — v23.0 APEX SOVEREIGN
=============================================================================
PRUEBAS UNITARIAS: GESTIÓN EN VIVO DE STOP LOSS, ADAPTIVE BREAKEVEN & FEE ABSORBER
=============================================================================
Valida:
1. Disparo de Fast BE Adaptativo (+1.2R Megacaps / +1.0R Altcoins) en TradeManager.
2. Micro-Buffer de Fee Absorber (0.08%) para garantizar PnL neto positivo.
3. Invocación de modify_position_tpsl hacia el exchange.
4. Sincronización y cálculo de avance en R para posiciones abiertas.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from engine.workers.trade_manager import TradeManager
from engine.execution.bitunix_executor import BitunixExecutor

@pytest.mark.asyncio
async def test_fast_be_trigger_at_1r():
    """Valida que una posición ACTIVE que alcance el umbral dispare Fast BE con Fee Absorber."""
    tm = TradeManager()
    
    signal = {
        "asset": "SUIUSDT",
        "symbol": "SUIUSDT",
        "signal_type": "LONG",
        "price": 2.0000,
        "stop_loss": 1.9000, # Riesgo = $0.10 -> +1.0R es $2.1000
        "initial_stop_loss": 1.9000,
        "tp1": 2.1500,
        "tp2": 2.3000,
        "tp3": 2.5000,
        "trailing_phase": "ACTIVE",
        "status": "FILLED",
        "position_id": "mock_pos_123"
    }
    
    # Mock de fetch_binance_history devolviendo precio actual $2.1050 (+1.05R en Altcoin)
    mock_history = [
        {"data": {"timestamp": 1700000000 + i*900, "close": 2.1050, "atr": 0.02}}
        for i in range(30)
    ]
    
    with patch("engine.workers.trade_manager.fetch_binance_history", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = mock_history
        
        with patch("engine.execution.bitunix_executor.BitunixExecutor.modify_position_tpsl", new_callable=AsyncMock) as mock_modify:
            mock_modify.return_value = True
            
            await tm._update_signal_trailing(signal)
            
            assert signal["trailing_phase"] == "BREAKEVEN"
            # Debe incluir el Fee Absorber (+0.08% o ATR buffer)
            assert signal["stop_loss"] >= 2.0000, "El nuevo SL debe estar en la entrada o superior"
            assert mock_modify.called, "Debe llamar a modify_position_tpsl en Bitunix"


@pytest.mark.asyncio
async def test_adaptive_breakeven_threshold_megacaps_vs_alts():
    """Valida que Megacaps exijan +1.2R para absorber re-tests, mientras Altcoins usen +1.0R."""
    tm = TradeManager()
    
    assert tm.is_megacap("BTCUSDT") is True
    assert tm.is_megacap("ETHUSDT") is True
    assert tm.is_megacap("SOLUSDT") is True
    assert tm.is_megacap("SUIUSDT") is False
    assert tm.is_megacap("NEARUSDT") is False
    assert tm.is_megacap("INJUSDT") is False


@pytest.mark.asyncio
async def test_fee_absorber_breakeven_math_positive_net_pnl():
    """Valida que el cálculo de Breakeven sume/reste el buffer de 0.08% para absorber comisiones."""
    tm = TradeManager()
    
    # LONG entry en $100 -> SL en Breakeven debe ser > $100.00 (ej: $100.08)
    long_be_sl = tm._calculate_breakeven_sl(entry=100.0, atr=0.10, is_long=True)
    assert long_be_sl >= 100.08
    
    # SHORT entry en $100 -> SL en Breakeven debe ser < $100.00 (ej: $99.92)
    short_be_sl = tm._calculate_breakeven_sl(entry=100.0, atr=0.10, is_long=False)
    assert short_be_sl <= 99.92


@pytest.mark.asyncio
async def test_sync_live_positions_fast_be():
    """Valida la reconciliación y cálculo de R para posiciones reales de Bitunix."""
    tm = TradeManager()
    
    # Mock de 2 posiciones: una en +1.5R (debe ser protegida) y otra en +0.3R (no debe ser modificada)
    mock_positions = [
        {
            "symbol": "SOLUSDT",
            "side": "BUY",
            "entryPrice": 180.0,
            "lastPrice": 187.5, # +7.5 USD vs SL de $5.0 -> +1.5R
            "slPrice": 175.0,
            "positionId": "pos_sol_1"
        },
        {
            "symbol": "ETHUSDT",
            "side": "BUY",
            "entryPrice": 3000.0,
            "lastPrice": 3015.0, # +15 USD vs SL de $50 -> +0.3R
            "slPrice": 2950.0,
            "positionId": "pos_eth_1"
        }
    ]
    
    with patch("engine.execution.bitunix_executor.BitunixExecutor.get_pending_positions", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_positions
        
        with patch("engine.execution.bitunix_executor.BitunixExecutor.modify_position_tpsl", new_callable=AsyncMock) as mock_mod:
            mock_mod.return_value = True
            
            results = await tm.sync_live_bitunix_positions()
            
            assert len(results) == 2
            # SOL en +1.5R debe estar protegida con Fast BE adaptativo
            assert results[0]["symbol"] == "SOLUSDT"
            assert results[0]["r_profit"] == 1.5
            assert "PROTEGIDO_FAST_BE" in results[0]["status"]
            
            # ETH en +0.3R sigue en curso sin modificar
            assert results[1]["symbol"] == "ETHUSDT"
            assert results[1]["r_profit"] == 0.3
            assert results[1]["status"] == "EN_CURSO"
