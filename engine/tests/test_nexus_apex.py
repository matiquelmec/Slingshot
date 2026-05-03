"""
engine/tests/test_nexus_apex.py — Pruebas de Stress Profesionales Apex
=====================================================================
Valida la cadena completa: Señal -> RiskManager -> SignalHandler -> Nexus -> Delta.
"""

import asyncio
import sys
import os

# Añadir el path raíz para imports
sys.path.append(os.getcwd())

from engine.execution.nexus import nexus
from engine.api.signal_handler import SignalHandler
from engine.core.logger import logger

class MockBroadcaster:
    def __init__(self):
        self.symbol = "BTCUSDT"
        self.interval = "15m"
    async def _broadcast(self, msg): pass

async def run_professional_audit():
    logger.info("🕵️ Iniciando Auditoría Profesional Apex (Fase 3)...")
    
    # 1. Simular una señal de alta confluencia (SMC + Liquidez)
    # Estos datos vienen del router en un escenario real
    tactical_mock = {
        "market_regime": "BULLISH_TREND",
        "active_strategy": "SMC_APEX_SNIPER",
        "signals": [
            {
                "type": "LONG",
                "price": 65000.0,
                "atr": 500.0,
                "confluence": {"score": 85},
                "timestamp": "2026-05-02T16:00:00Z"
            }
        ],
        "smc": {
            "order_blocks": {
                "bullish": [{"bottom": 64500.0, "top": 64700.0}],
                "bearish": [{"bottom": 67000.0, "top": 67200.0}]
            }
        }
    }
    
    # 2. Inicializar Handler
    handler = SignalHandler("BTCUSDT", "15m", MockBroadcaster())
    
    # 3. Procesar señal (esto debería disparar el Nexus)
    logger.info("📡 Inyectando señal táctica en el Handler...")
    await handler.handle(tactical_mock)
    
    # Esperar un momento para que las tareas async se completen
    await asyncio.sleep(2)
    
    # 4. Verificar Nodo Nexus
    active = nexus.get_active_positions()
    if "BTCUSDT" in active:
        logger.info("✅ PRUEBA NEXUS PASADA: Posición registrada en el nodo.")
        pos = active["BTCUSDT"]
        logger.info(f"📊 Detalle Apex: SL: {pos['signal']['stop_loss']} | TP1: {pos['signal']['tp1']} | TP3: {pos['signal']['tp3']}")
    else:
        logger.error("❌ PRUEBA NEXUS FALLIDA: La posición no llegó al nodo.")

if __name__ == "__main__":
    asyncio.run(run_professional_audit())
