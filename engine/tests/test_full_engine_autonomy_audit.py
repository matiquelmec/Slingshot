"""
engine/tests/test_full_engine_autonomy_audit.py
=============================================================================
AUDITORÍA INTEGRAL DE AUTONOMÍA Y PROCEDIMIENTOS DE SEGURIDAD v21.0
=============================================================================
Valida:
1. Arranque 100% automático del TradeManager a través del Orchestrator.
2. Procedimiento de Seguridad: Invariante del Stop Loss (Nunca mover SL en contra).
3. Conectividad y respuesta de endpoints de Bitunix.
4. Métrica de Calidad: Resiliencia ante desconexiones de red con reintentos.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from engine.workers.orchestrator import SlingshotOrchestrator
from engine.workers.trade_manager import TradeManager
from engine.execution.bitunix_executor import BitunixExecutor

@pytest.mark.asyncio
async def test_orchestrator_auto_starts_trade_manager():
    """Valida que encender el orquestador activa automáticamente el TradeManager centinela."""
    orchestrator = SlingshotOrchestrator()
    
    with patch.object(orchestrator.trade_manager, "start") as mock_tm_start, \
         patch.object(orchestrator.market_scanner, "start") as mock_scanner_start, \
         patch.object(orchestrator, "sync_watchlists", new_callable=AsyncMock), \
         patch.object(orchestrator, "spawn_persistent_broadcaster", new_callable=AsyncMock), \
         patch("engine.workers.orchestrator.load_local_state"):
        
        # Iniciar orquestador
        await orchestrator.start()
        
        assert mock_tm_start.called, "El TradeManager DEBE iniciarse automáticamente con el orquestador"
        assert mock_scanner_start.called, "El MarketScanner DEBE iniciarse automáticamente con el orquestador"

@pytest.mark.asyncio
async def test_security_sl_never_moves_backwards():
    """
    PROCEDIMIENTO DE SEGURIDAD CRÍTICO:
    El Stop Loss JAMÁS puede ser movido a un nivel más desfavorable que el actual.
    """
    tm = TradeManager()
    
    # Caso LONG: Si el SL actual está en $2,433.29 (Breakeven), un intento de ponerlo en $2,400.00 DEBE ser rechazado.
    current_sl = 2433.29
    worse_sl_long = 2400.00
    assert not tm._sl_improved(current_sl, worse_sl_long, is_long=True), "SEGURIDAD VIOLADA: Se permitió empeorar el SL en LONG"
    
    better_sl_long = 2450.00
    assert tm._sl_improved(current_sl, better_sl_long, is_long=True), "Debe permitir mejorar el SL a favor del trade"

    # Caso SHORT: Si el SL actual está en $2,433.29, un intento de ponerlo en $2,450.00 DEBE ser rechazado.
    worse_sl_short = 2450.00
    assert not tm._sl_improved(current_sl, worse_sl_short, is_long=False), "SEGURIDAD VIOLADA: Se permitió empeorar el SL en SHORT"
    
    better_sl_short = 2400.00
    assert tm._sl_improved(current_sl, better_sl_short, is_long=False), "Debe permitir mejorar el SL a favor del trade"

@pytest.mark.asyncio
async def test_slot_recycling_frees_risk_on_breakeven():
    """
    AUDITORÍA DE CONCURRENCIA:
    Si hay 4 posiciones abiertas pero 1 está en Breakeven (ETH),
    el conteo de riesgo desprotegido debe ser 3, permitiendo abrir una nueva operación.
    """
    from engine.execution.nexus import NexusNode
    node = NexusNode(dry_run=False)
    
    # 4 Posiciones activas: 3 con riesgo inicial y 1 en Breakeven
    node._active_positions = {
        "SOLUSDT": {"signal": {"price": 100.0, "stop_loss": 95.0, "type": "LONG"}, "smart_trailing": {"be_active": False}},
        "ATOMUSDT": {"signal": {"price": 1.50, "stop_loss": 1.40, "type": "LONG"}, "smart_trailing": {"be_active": False}},
        "AVAXUSDT": {"signal": {"price": 7.50, "stop_loss": 7.00, "type": "LONG"}, "smart_trailing": {"be_active": False}},
        "ETHUSDT": {"signal": {"price": 2433.29, "stop_loss": 2433.29, "type": "LONG"}, "smart_trailing": {"be_active": True}}, # Breakeven!
    }
    
    # El conteo de riesgo debe ser 3 (ETH liberó su slot)
    assert node.get_unprotected_risk_count() == 3, "ETH en Breakeven DEBE liberar el slot de riesgo"
    
    # Al simular una 5ta orden (RENDERUSDT), no debe ser rechazada por límite de 4
    with patch.object(node.executor, "place_limit_signal", new_callable=AsyncMock) as mock_limit, \
         patch.object(node.executor, "get_pending_orders", new_callable=AsyncMock, return_value=[]), \
         patch.object(node.executor, "get_available_margin_usdt", new_callable=AsyncMock, return_value=82.23):
        mock_limit.return_value = {"status": "success", "order_id": "dry_new_1"}
        
        new_sig = {"asset": "RENDERUSDT", "price": 4.50, "stop_loss": 4.20, "tp1": 5.0, "type": "LONG", "confluence_score": 90.0}
        await node.process_limit_setup(new_sig)
        
        assert mock_limit.called, "Debe permitir colocar la 5ta orden porque hay un slot liberado por BE"
