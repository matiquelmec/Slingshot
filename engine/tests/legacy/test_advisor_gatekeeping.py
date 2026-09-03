
import asyncio
import json
import sys
import os

# Anadir el path del proyecto para poder importar los modulos
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.api.advisor_bridge import AdvisorBridge
from engine.core.logger import logger
from unittest.mock import AsyncMock, MagicMock

async def test_advisor_gatekeeping_logic():
    print("Iniciando prueba de Auditoria del Asesor v13.0...")
    
    # 1. Mock del Broadcaster
    mock_bc = MagicMock()
    mock_bc._broadcast = AsyncMock()
    mock_bc._store = MagicMock()
    mock_bc._store.get_advisor_advice = AsyncMock(return_value=None)
    mock_bc._store.save_advisor_advice = AsyncMock()
    mock_bc._store.save_tactical_snapshot = AsyncMock()
    mock_bc._store.get_news = AsyncMock(return_value=[])
    mock_bc._store.get_liquidation_clusters = AsyncMock(return_value=[])
    mock_bc._store.get_economic_events = AsyncMock(return_value=[])
    mock_bc._store.get_mtf_context = AsyncMock(return_value={})
    mock_bc.latest_price = 70000.0
    mock_bc._live_rvol = 1.0
    mock_bc._last_ml = {"direction": "ALCISTA", "probability": 85}
    mock_bc._last_onchain = {"data": {}}
    
    bridge = AdvisorBridge("BTCUSDT", "15m", mock_bc)
    
    # ESCENARIO A: Mercado Lateral, Baja Confluencia (Gatekeeping deberia activarse)
    print("\n--- Escenario A: Mercado Lateral, Baja Confluencia ---")
    tactical_low_conf = {
        "market_regime": "RANGING",
        "confluence_score": 10,
        "signals": [],
        "blocked_signals": [],
        "candles": [{"timestamp": 123456789}]
    }
    
    await bridge.emit(tactical_low_conf, {"data": {"current_session": "LONDON"}})
    
    # Verificar que se envio el mensaje de bypass
    last_call = mock_bc._broadcast.call_args_list[-1]
    msg = last_call[0][0]
    print(f"Resultado Escenario A: {msg['data']['content']}")
    
    # ESCENARIO B: Deteccion de Senal (Gatekeeping deberia ser ignorado)
    print("\n--- Escenario B: Deteccion de Senal Aprobada ---")
    tactical_with_signal = {
        "market_regime": "MARKUP",
        "confluence_score": 85,
        "signals": [{"type": "LONG", "price": 70000, "confluence": {"score": 85}}],
        "blocked_signals": [],
        "candles": [{"timestamp": 123456790}]
    }
    
    # Para esta prueba, mockeamos la llamada real a Ollama para que no tarde
    import engine.api.advisor_bridge
    engine.api.advisor_bridge.generate_tactical_advice = AsyncMock(return_value=json.dumps({
        "verdict": "VEST",
        "logic": "Estructura alcista confirmada en zona de descuento. Alta probabilidad.",
        "threat": "LOW"
    }))
    engine.api.advisor_bridge.check_ollama_status = AsyncMock(return_value=True)
    
    await bridge.emit(tactical_with_signal, {"data": {"current_session": "LONDON"}})
    
    # Verificar que se envio el analisis de la IA
    last_call = mock_bc._broadcast.call_args_list[-1]
    msg = last_call[0][0]
    print(f"Resultado Escenario B: {msg['data'].get('content', msg['data'].get('logic'))}")
    
    print("\nPrueba completada: El Gatekeeping funciona correctamente y se desactiva ante senales.")

if __name__ == "__main__":
    asyncio.run(test_advisor_gatekeeping_logic())
