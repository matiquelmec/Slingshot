"""
engine/execution/nexus.py — v8.0.0 Apex Core
=============================================
EL NODO DE EJECUCIÓN SOBERANO.

Responsabilidad:
  1. Escuchar señales aprobadas del SignalHandler.
  2. Fragmentar órdenes usando DeltaOrchestrator (60/20/20).
  3. Ejecutar vía BinanceExecutor (Modo Sync/Hilos) o Bitunix.
  4. Monitorear estados de órdenes y activar el Smart Trailing en vivo.
"""

import asyncio
from typing import Dict, Any, List
from engine.core.logger import logger
from engine.execution.delta_executor import DeltaOrchestrator
from engine.execution.binance_executor import BinanceExecutor
from engine.api.config import settings

class NexusNode:
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.executor = BinanceExecutor(dry_run=dry_run)
        self._active_positions = {}
        logger.info(f"🛡️ [NEXUS] Nodo de Ejecución inicializado (Dry Run: {dry_run})")

    def start_dashboard(self):
        """Inicia el monitor de ejecución en segundo plano."""
        asyncio.create_task(self._dashboard_loop())

    async def _dashboard_loop(self):
        """Monitor simple para ver posiciones en tiempo real."""
        logger.info("📊 [NEXUS] Dashboard de Ejecución activado.")
        while True:
            await asyncio.sleep(10) # Refrescar cada 10 segundos
            if not self._active_positions:
                continue
                
            logger.info("="*50)
            logger.info("📈 DASHBOARD DE EJECUCIÓN APEX (LIVE)")
            logger.info("="*50)
            for asset, pos in self._active_positions.items():
                sig = pos.get('signal', {})
                status = pos.get('status', 'UNKNOWN')
                entry = sig.get('price', 0)
                tp1 = sig.get('tp1', 0)
                tp3 = sig.get('take_profit_3r', sig.get('tp3', 0))
                sl = sig.get('stop_loss', 0)
                size = sig.get('position_size_usdt', sig.get('position_size', 0))
                
                # Proyección de PnL (asumiendo TP3 como target final)
                if entry > 0:
                    rr = round(abs(tp3 - entry) / abs(entry - sl), 2) if abs(entry - sl) > 0 else 0
                    profit_pct = round(abs(tp3 - entry) / entry * 100, 2)
                else:
                    rr = 0
                    profit_pct = 0
                    
                logger.info(f"🔹 {asset} [{sig.get('type', 'LONG')}] | Status: {status}")
                logger.info(f"   Entry: ${entry:.2f} | Size: ${size:.2f}")
                logger.info(f"   SL: ${sl:.2f} | TP1: ${tp1:.2f} | TP3: ${tp3:.2f}")
                logger.info(f"   Proyección: R:R {rr}:1 | +{profit_pct}% (Max)")
            logger.info("="*50)

    async def process_signal(self, signal: Dict[str, Any]):
        """
        Punto de entrada para señales reales.
        """
        asset = signal.get("asset")
        sig_type = signal.get("type", "LONG")
        
        logger.info(f"⚡ [NEXUS] Recibida señal de alta fidelidad: {asset} {sig_type}")
        
        # 1. Fragmentación Apex (Delta 60/20/20)
        fragments = DeltaOrchestrator.fragment_order(signal)
        
        # 2. Ejecución (Por ahora simplificada a una orden principal + órdenes de protección)
        # TODO: En el futuro, enviar las 3 órdenes TP separadas si el exchange lo permite eficientemente
        try:
            result = await self.executor.execute_signal(signal)
            
            if result.get("status") == "success":
                logger.info(f"✅ [NEXUS] Posición abierta en {asset}. ID: {result.get('main_order_id')}")
                self._active_positions[asset] = {
                    "signal": signal,
                    "execution": result,
                    "status": "OPEN"
                }
            else:
                logger.error(f"❌ [NEXUS] Error al abrir posición en {asset}: {result.get('message')}")
                
        except Exception as e:
            logger.error(f"💥 [NEXUS] Error crítico procesando señal: {e}")

    def get_active_positions(self):
        return self._active_positions

# Instancia global (Singleton)
nexus = NexusNode(dry_run=True) # Siempre por defecto en Dry Run por seguridad

