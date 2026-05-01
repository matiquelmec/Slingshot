from engine.core.logger import logger
import asyncio
from typing import List, Dict, Optional
from engine.api.config import settings
from engine.api.registry import registry
import engine.indicators.macro as macro
from engine.indicators.ghost_data import refresh_ghost_data, load_local_state, get_ghost_state
from engine.indicators.onchain_provider import refresh_all_onchain
from engine.core.session_manager import SessionManager
from engine.workers.news_worker import NewsWorker
from engine.workers.calendar_worker import CalendarWorker

class SlingshotOrchestrator:
    """
    EL DIRECTOR DE ORQUESTA (v3.2 - Local Master Edition).
    Mantiene vivos los broadcasters de los activos VIP en segundo plano.
    Asegura que el MemoryStore esté siempre alimentado para el Radar.
    """
    def __init__(self, radar_assets: Optional[List[str]] = None):
        # Activos dinámicos (se cargarán desde DB en start)
        self.radar_assets: set = set()
        self.intervals = ["1m", "5m", "15m"] 
        self._tasks: Dict[str, asyncio.Task] = {}
        self._stop_event = asyncio.Event()
        self.news_worker = NewsWorker()
        self.calendar_worker = CalendarWorker()

    async def start(self):
        logger.info(f"🚀 [ORCHESTRATOR] Iniciando Motor Local Master (Modo 100% Dinámico)...")
        
        # Sincronización inicial para poblar radar_assets
        load_local_state() # Cargar datos macro previos si existen
        await self.sync_watchlists()
        
        # Iniciar Worker de Radar Macro (Ghost Data)
        asyncio.create_task(self._ghost_worker())
        # Iniciar Worker de Métricas On-Chain Centralizadas (v8.5.9)
        asyncio.create_task(self._onchain_worker())
        # Iniciar Worker de Sesiones Globales
        asyncio.create_task(self._session_worker())
        # Iniciar Worker de Noticias en Tiempo Real
        asyncio.create_task(self.news_worker.start())
        # Iniciar Worker de Calendario Económico
        asyncio.create_task(self.calendar_worker.start())
        
        # Si la DB está vacía, podemos poner BTC por defecto para que el motor no esté ocioso
        if not self.radar_assets:
            logger.info("ℹ️ [ORCHESTRATOR] Watchlist vacía. Usando BTCUSDT como activo de guardia.")
            for interval in self.intervals:
                await self.spawn_persistent_broadcaster("BTCUSDT", interval)
            self.radar_assets.add("BTCUSDT")

        logger.info(f"✅ [ORCHESTRATOR] Malla de vigilancia activa para: {self.radar_assets} en {self.intervals}")
        
        # Loop de auditoría y mantenimiento
        while not self._stop_event.is_set():
            try:
                await self.sync_watchlists()
                await self.audit_health()
            except Exception as e:
                logger.error(f"⚠️ [ORCHESTRATOR] Error en mantenimiento: {e}")
            
            await asyncio.sleep(30) # Sincronización cada 30 segundos

    async def spawn_persistent_broadcaster(self, symbol: str, interval: str):
        """Crea un broadcaster que no se destruye aunque no haya usuarios."""
        try:
            broadcaster, client_id = await registry.get_or_create(symbol, interval, persistent=True)
            key = f"{symbol.upper()}:{interval}"
            logger.info(f"📦 [ORCHESTRATOR] Sensor {key} garantizado en background.")
        except Exception as e:
            logger.info(f"❌ [ORCHESTRATOR] No se pudo activar {symbol}:{interval}: {e}")

    async def sync_watchlists(self):
        """
        En v5.7.155 Master Gold, restringimos estrictamente la vigilancia a los activos VIP
        para garantizar latencia cero y optimización de recursos.
        """
        vip_assets = set(settings.MASTER_WATCHLIST)
        
        # 1. Eliminar activos que ya no son VIP (si existieran)
        to_remove = self.radar_assets - vip_assets
        for sym in to_remove:
            logger.info(f"🧹 [ORCHESTRATOR] Removiendo activo no-VIP: {sym}")
            # En v3.0 simplemente dejamos de vigilarlos, el registry limpiará si no hay clientes
            self.radar_assets.remove(sym)

        # 2. Asegurar que todos los VIP estén activos en todas las temporalidades
        new_assets = vip_assets - self.radar_assets
        if new_assets:
            logger.info(f"✨ [ORCHESTRATOR] Activando Sensores VIP: {new_assets}")
            for sym in new_assets:
                for interval in self.intervals:
                    asyncio.create_task(self.spawn_persistent_broadcaster(sym, interval))
                self.radar_assets.add(sym)

    async def audit_health(self):
        """Verifica que todos los activos VIP tengan un broadcaster activo en el registry."""
        for symbol in self.radar_assets:
            for interval in self.intervals:
                key = f"{symbol.upper()}:{interval}"
                if key not in registry._broadcasters:
                    logger.info(f"🚨 [ORCHESTRATOR] Alerta: Sensor {key} caído. Reiniciando...")
                    await self.spawn_persistent_broadcaster(symbol, interval)

    async def _ghost_worker(self):
        """
        [MACRO SENTINEL v8.6.0] Refresca los datos macro globales cada 15 min.
        Centraliza las peticiones pesadas (DXY, NASDAQ, F&G, BTC.D) para todos los sensores.
        """
        logger.info("🔮 [ORCHESTRATOR] Macro Sentinel activado.")
        
        # Sincronización FORZADA al inicio
        try:
            await macro.update_macro_context()
            m_ctx = macro.get_macro_context()
            # 🚀 El Orchestrator es el ÚNICO que hace global_only=True
            await refresh_ghost_data(global_only=True, macro_ctx=m_ctx)
        except Exception as e:
            logger.error(f"⚠️ [ORCHESTRATOR] Error en Sentinel inicial: {e}")

        while not self._stop_event.is_set():
            try:
                # 1. Actualizar Capa 1: Contexto Global (DXY/NASDAQ)
                await macro.update_macro_context()
                m_ctx = macro.get_macro_context()

                # 2. Refrescar métricas globales pesadas
                state = await refresh_ghost_data(global_only=True, macro_ctx=m_ctx)
                
                # 3. Propagar la actualización a todos los activos bajo vigilancia
                # Esto obliga a cada broadcaster a recalcular su bias con el nuevo caché global
                # y enviar el 'ghost_update' a sus clientes conectados.
                for broadcaster in registry._broadcasters.values():
                    if hasattr(broadcaster, '_advisor_bridge'):
                        asyncio.create_task(broadcaster._advisor_bridge.refresh_ghost())

                logger.info(f"[ORCHESTRATOR] 🔮 Macro Sentinel sincronizado: {state.macro_bias} (F&G: {state.fear_greed_value})")
            except Exception as e:
                logger.error(f"⚠️ [ORCHESTRATOR] Error en ciclo Sentinel: {e}")
            
            # Esperar 5 minutos (300s) para mantener el radar vivo (v8.7.1)
            await asyncio.sleep(300)

    async def _session_worker(self):
        """Worker que sincroniza el estado de las sesiones globales cada minuto."""
        logger.info("🕒 [ORCHESTRATOR] Sincronizador de Sesiones Globales activo.")
        last_session = None
        
        while not self._stop_event.is_set():
            try:
                # Obtener estado global (basado en tiempo)
                status = SessionManager.get_global_session_status()
                current = status["current_session"]
                
                # Solo hacer broadcast si la sesión cambió o cada 5 minutos por seguridad
                if current != last_session:
                    logger.info(f"[ORCHESTRATOR] 🌎 Cambio de Sesión detectado: {current}")
                    last_session = current
                    
                    # Hacer broadcast a todos los broadcasters activos
                    payload = {"type": "session_update", "data": status}
                    for broadcaster in registry._broadcasters.values():
                        await broadcaster._broadcast(payload)
                        
            except Exception as e:
                logger.error(f"⚠️ [ORCHESTRATOR] Error en Worker de Sesiones: {e}")
            
            # Revisar cada 1 minuto (60s)
            await asyncio.sleep(60)

    def stop(self):
        """Parada coordinada."""
        self._stop_event.set()
        logger.info("[ORCHESTRATOR] Deteniendo motor maestro...")

    async def _onchain_worker(self):
        """Worker centralizado para telemetría institucional (v8.8.1)."""
        logger.info("📡 [ORCHESTRATOR] OnChain Sentinel activado.")
        
        # 🚀 Primer refresco inmediato para evitar valores '0' al inicio
        try:
            await self.sync_watchlists()
            if self.radar_assets:
                await refresh_all_onchain(list(self.radar_assets))
        except Exception as e:
            logger.error(f"❌ [ORCHESTRATOR] Error en refresco inicial OnChain: {e}")

        while not self._stop_event.is_set():
            try:
                if self.radar_assets:
                    # 1. Refrescar caché global
                    await refresh_all_onchain(list(self.radar_assets))
                    
                    # 2. Propagar a los broadcasters activos para refresco visual (v8.8.1)
                    for broadcaster in registry._broadcasters.values():
                        try:
                            # Forzar un ghost refresh que incluya la nueva data onchain
                            if hasattr(broadcaster, '_refresh_ghost'):
                                asyncio.create_task(broadcaster._refresh_ghost())
                        except: pass
                        
                logger.debug("[ORCHESTRATOR] 📡 OnChain Sentinel sincronizado.")
            except Exception as e:
                logger.error(f"⚠️ [ORCHESTRATOR] Error en On-Chain worker: {e}")
            
            # Sincronización cada 60s (v8.8.1)
            await asyncio.sleep(60)

async def run_orchestrator():
    orchestrator = SlingshotOrchestrator()
    try:
        await orchestrator.start()
    except KeyboardInterrupt:
        pass
    finally:
        orchestrator.stop()

if __name__ == "__main__":
    asyncio.run(run_orchestrator())
