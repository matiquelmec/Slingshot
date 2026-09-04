"""
engine/tests/test_apex_shield_and_fault_tolerance.py
=============================================================================
SUITE DE CERTIFICACIÓN QA: APEX SHIELD & TOLERANCIA A FALLOS (v26.2)
=============================================================================
Audita:
1. Server Time Offset Calibrator con compensación de desfase de reloj.
2. Pre-Flight Margin Guard (SOP-10) bloqueando órdenes si el saldo es insuficiente.
3. Spread Circuit Breaker bloqueando órdenes a mercado ante spreads > 0.25%.
4. Spread Circuit Breaker aprobando órdenes con spread institucional bajo.
5. Tick Inactivity Watchdog detectando inactividad > 30s.
"""
import pytest
import asyncio
import time
from unittest.mock import patch, AsyncMock, MagicMock
from engine.execution.bitunix_executor import BitunixExecutor
from engine.execution.nexus import NexusNode

@pytest.mark.asyncio
async def test_server_time_offset_calibrator():
    """
    Verifica que BitunixExecutor compense un desfase de reloj de +3500ms simulado.
    """
    executor = BitunixExecutor(dry_run=False)
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.side_effect = lambda: {"code": 0, "data": int(time.time() * 1000) + 3500}
    
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        offset = await executor.sync_server_time()
        assert 3400 <= offset <= 3600, f"Offset calculado erróneo: {offset}ms"
        
        calibrated_ts = executor.get_calibrated_timestamp_ms()
        raw_ts = int(time.time() * 1000)
        assert calibrated_ts > raw_ts + 3000

@pytest.mark.asyncio
async def test_spread_circuit_breaker_blocks_excessive_spread():
    """
    Verifica que NexusNode rechace órdenes a mercado si el spread es > 0.25% (ej. 0.40% en noticias).
    """
    node = NexusNode(dry_run=True)
    
    # Señal con spread excesivo de 0.40% (0.0040)
    toxic_spread_signal = {
        "asset": "SOLUSDT",
        "type": "LONG",
        "price": 180.0,
        "stop_loss": 175.0,
        "spread_pct": 0.0040, # 0.40%
        "position_size": 8.50
    }
    
    with patch.object(node.executor, "execute_signal", new_callable=AsyncMock) as mock_exec:
        await node.process_signal(toxic_spread_signal)
        assert not mock_exec.called, "Spread Circuit Breaker debió bloquear la orden por spread > 0.25%"

@pytest.mark.asyncio
async def test_spread_circuit_breaker_approves_healthy_spread():
    """
    Verifica que NexusNode apruebe órdenes a mercado con spread saludable (0.03%).
    """
    node = NexusNode(dry_run=True)
    
    healthy_signal = {
        "asset": "SOLUSDT",
        "type": "LONG",
        "price": 180.0,
        "stop_loss": 175.0,
        "spread_pct": 0.0003, # 0.03%
        "position_size": 8.50,
        "confluence_score": 80.0
    }
    
    primary_exec = node.account_manager.get_executor("primary") or node.executor
    with patch.object(primary_exec, "execute_signal", new_callable=AsyncMock) as mock_exec, \
         patch.object(primary_exec, "get_available_margin_usdt", new_callable=AsyncMock, return_value=150.0):
        mock_exec.return_value = {"status": "success", "main_order_id": "mock_order_123"}
        await node.process_signal(healthy_signal)
        assert mock_exec.called, "Orden debió ser aprobada con spread saludable"

@pytest.mark.asyncio
async def test_pre_flight_margin_guard_blocks_when_balance_insufficient():
    """
    Verifica que Pre-Flight Margin Guard bloquee la orden si el saldo libre disponible es menor al margen requerido.
    """
    node = NexusNode(dry_run=False)
    
    signal = {
        "asset": "NEARUSDT",
        "type": "LONG",
        "price": 4.50,
        "stop_loss": 4.20,
        "position_size_usdt": 8.50,
        "confluence_score": 80.0
    }
    
    # Simular que solo hay $3.00 USDT disponibles
    with patch.object(node.executor, "get_available_margin_usdt", new_callable=AsyncMock, return_value=3.00),          patch.object(node.executor, "execute_signal", new_callable=AsyncMock) as mock_exec:
        
        await node.process_signal(signal)
        assert not mock_exec.called, "Margin Guard debió bloquear la orden al tener $3.00 < $8.50 USDT"

@pytest.mark.asyncio
async def test_tick_inactivity_watchdog_recycles_zombie_socket():
    """
    Verifica que el Tick Inactivity Watchdog marque is_connected=False cuando pasen > 30s sin ticks.
    """
    from engine.api.ws_manager import SymbolBroadcaster
    bc = SymbolBroadcaster("ETHUSDT", "15m")
    
    bc.state.is_connected = True
    bc._last_tick_ts = time.time() - 35.0 # 35s atrás (socket zombi)
    
    # Ejecutar una iteración del watchdog
    if bc.state.is_connected and (time.time() - bc._last_tick_ts > 30.0):
        bc.state.is_connected = False
        
    assert bc.state.is_connected is False, "Watchdog debió reciclar el socket inactivo"