"""
engine/execution/nexus.py — v11.1 APEX SOVEREIGN (Audited)
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
from engine.core.memory import blackbox
from engine.core.store import store


class NexusNode:
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.executor = BinanceExecutor(dry_run=dry_run)
        self._active_positions = {}
        logger.info(f"🛡️ [NEXUS] Nodo de Ejecución inicializado (Dry Run: {dry_run})")
        
        # Iniciar Centinelas de Riesgo
        self.start_centinels()

    def start_centinels(self):
        """Inicia los procesos de monitoreo y gestión de riesgo."""
        loop = asyncio.get_event_loop()
        loop.create_task(self._dashboard_loop())
        loop.create_task(self._omega_centinel_loop())

    async def _omega_centinel_loop(self):
        """
        [OMEGA CENTINEL v10.2.0]
        Monitorea el precio en vivo y gestiona el Smart Trailing.
        """
        logger.info("👁️ [OMEGA] Centinela de Riesgo activado.")
        while True:
            await asyncio.sleep(5) # Ciclo de auditoría cada 5 segundos
            
            assets_to_remove = []
            for asset, pos in list(self._active_positions.items()):
                try:
                    # 1. Obtener precio actual (simplificado vía ticker)
                    ticker = await asyncio.to_thread(self.executor.client.fetch_ticker, asset.replace('/', ''))
                    current_price = ticker['last']
                    
                    sig = pos['signal']
                    entry = sig['price']
                    tp1 = sig['tp1']
                    sl = sig['stop_loss']
                    is_long = sig['type'] == "LONG"
                    
                    # 2. Verificar si se ha alcanzado el TP1 para mover a BE
                    be_active = pos.get("smart_trailing", {}).get("be_active", False)
                    
                    if not be_active:
                        target_hit = (current_price >= tp1) if is_long else (current_price <= tp1)
                        if target_hit:
                            logger.info(f"🎯 [OMEGA] {asset} alcanzó TP1. Activando SMART TRAILING (Mover a BE)...")
                            # Mover SL a Entry + Pequeño buffer para comisiones
                            new_sl = entry * 1.0005 if is_long else entry * 0.9995
                            
                            # Cancelar SL antiguo y poner nuevo (Simulado en Nexus por ahora)
                            # En producción, llamaríamos a self.executor.update_stop_loss(asset, new_sl)
                            pos["signal"]["stop_loss"] = new_sl
                            pos["smart_trailing"] = {"be_active": True, "trailing_active": True}
                            logger.info(f"🛡️ [OMEGA] SL de {asset} movido a BE: ${new_sl:.2f}")

                    # 4. 🚀 [YOSH v13.1] AVERAGING UP (Escalado en Ganancia)
                    # Si ya estamos en BE y el precio retrocede a una zona de VALOR, añadir contratos.
                    can_scale = be_active and not pos.get("averaging_up_done", False)
                    if can_scale:
                        session_state = store.get_session_state(asset)
                        vp = (session_state or {}).get("volume_profile", {})
                        
                        if vp and vp.get("vah"):
                            poc = vp["poc"]
                            vah = vp["vah"]
                            val = vp["val"]
                            
                            # Criterio: El precio retrocede al POC o VAL/VAH (dependiendo de la dirección)
                            target_ref = poc # Usamos el POC como imán de valor principal
                            retest_zone = (current_price <= target_ref * 1.001 and current_price >= target_ref) if is_long else \
                                          (current_price >= target_ref * 0.999 and current_price <= target_ref)
                            
                            if retest_zone:
                                logger.warning(f"📈 [YOSH] Retest de VALOR detectado en {asset} (${current_price:.2f}). Ejecutando AVERAGING UP...")
                                # Ejecutar adición del 50% del tamaño original
                                try:
                                    # En un sistema real: await self.executor.scale_position(asset, size * 0.5)
                                    pos["averaging_up_done"] = True
                                    pos["signal"]["position_size_usdt"] *= 1.5 # Simulación de aumento de tamaño
                                    logger.info(f"✅ [YOSH] Posición {asset} escalada exitosamente. Nuevo tamaño: ${pos['signal']['position_size_usdt']:.2f}")
                                except Exception as scale_err:
                                    logger.error(f"❌ [YOSH] Error al escalar posición: {scale_err}")

                    # 3. Verificar si la posición se ha cerrado (SL o TP3 final hit)
                    # Esto es una simplificación; un sistema real monitorearía WebSockets de órdenes
                    # 3. Verificar si la posición se ha cerrado (SL o TP3 final hit)
                    is_sl = (current_price <= sl) if is_long else (current_price >= sl)
                    is_tp = False
                    if not is_sl:
                        tp3 = sig.get('tp3', tp1 * 1.1)
                        is_tp = (current_price >= tp3) if is_long else (current_price <= tp3)
                        
                    if is_sl or is_tp:
                        result_str = "STOP_LOSS" if is_sl else "TAKE_PROFIT"
                        logger.info(f"🏁 [OMEGA] {asset} cerrado por {result_str}. Grabando en Black Box.")
                        
                        # Grabar en la caja negra para aprendizaje institucional
                        blackbox.record_trade(sig, result_str)
                        
                        assets_to_remove.append(asset)

                except Exception as e:
                    logger.error(f"⚠️ [OMEGA] Error auditando {asset}: {e}")

            for asset in assets_to_remove:
                del self._active_positions[asset]

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
        
        # 2. Ejecución de la Grilla
        try:
            result = await self.executor.execute_signal(signal, fragments=fragments)
            
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

