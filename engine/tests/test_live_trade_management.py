"""
engine/tests/test_live_trade_management.py
=============================================================================
PRUEBAS UNITARIAS: GESTIÓN EN VIVO DE STOP LOSS & FAST BREAKEVEN (BITUNIX)
=============================================================================
Valida:
1. Disparo inmediato de Fast BE al alcanzar +1.0R en TradeManager.
2. Invocación de modify_position_tpsl hacia el exchange.
3. Sincronización y cálculo de avance en R para posiciones abiertas.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from engine.workers.trade_manager import TradeManager
from engine.execution.bitunix_executor import BitunixExecutor

@pytest.mark.asyncio
async def test_fast_be_trigger_at_1r():
    """Valida que una posición ACTIVE que alcance +1.0R dispare Fast BE inmediatamente."""
    tm = TradeManager()
    
    signal = {
        "asset": "BTCUSDT",
        "symbol": "BTCUSDT",
        "signal_type": "LONG",
        "price": 95000.0,
        "stop_loss": 94000.0, # Riesgo = $1,000 -> +1.0R es $96,000
        "initial_stop_loss": 94000.0,
        "tp1": 96300.0,
        "tp2": 97200.0,
        "tp3": 98500.0,
        "trailing_phase": "ACTIVE",
        "status": "FILLED",
        "position_id": "mock_pos_123"
    }
    
    # Mock de fetch_binance_history devolviendo precio actual $96,050 (+1.05R)
    mock_history = [
        {"data": {"timestamp": 1700000000 + i*900, "close": 96050.0, "atr": 200.0}}
        for i in range(30)
    ]
    
    with patch("engine.workers.trade_manager.fetch_binance_history", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = mock_history
        
        with patch("engine.execution.bitunix_executor.BitunixExecutor.modify_position_tpsl", new_callable=AsyncMock) as mock_modify:
            mock_modify.return_value = True
            
            await tm._update_signal_trailing(signal)
            
            assert signal["trailing_phase"] == "BREAKEVEN"
            assert signal["stop_loss"] >= 95000.0, "El nuevo SL debe estar en la entrada o superior"
            assert mock_modify.called, "Debe llamar a modify_position_tpsl en Bitunix"

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
            # SOL en +1.5R debe estar protegida
            assert results[0]["symbol"] == "SOLUSDT"
            assert results[0]["r_profit"] == 1.5
            assert results[0]["status"] == "PROTEGIDO_FAST_BE"
            
            # ETH en +0.3R sigue en curso sin modificar
            assert results[1]["symbol"] == "ETHUSDT"
            assert results[1]["r_profit"] == 0.3
            assert results[1]["status"] == "EN_CURSO"
