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
from engine.execution.nexus import nexus
from engine.indicators.htf_analyzer import HTFAnalyzer
from engine.indicators.data_utils import fetch_binance_history
from engine.core.store import store
import pandas as pd
import time

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
        self.htf_analyzer = HTFAnalyzer()

    async def start(self):
        logger.info(f"🚀 [ORCHESTRATOR] Iniciando Motor Local Master (Modo 100% Dinámico)...")
        
        # Sincronización inicial para poblar radar_assets
        load_local_state() # Cargar datos macro previos si existen
        await self.sync_watchlists()
        
        # Iniciar Worker de Radar Macro (Ghost Data)
        asyncio.create_task(self._ghost_worker())
        # Iniciar Worker de Sesgo Fractal Centralizado (v10.0 Sovereign)
        asyncio.create_task(self._fractal_worker())
        # Iniciar Worker de Métricas On-Chain Centralizadas (v8.5.9)
        asyncio.create_task(self._onchain_worker())
        # Iniciar Worker de Sesiones Globales
        asyncio.create_task(self._session_worker())
        # Iniciar Worker de Noticias en Tiempo Real
        asyncio.create_task(self.news_worker.start())
        # Iniciar Worker de Calendario Económico
        asyncio.create_task(self.calendar_worker.start())
        
        # 🚀 [APEX] Iniciar Dashboard de Ejecución Nexus
        nexus.start_dashboard()
        
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

    async def _fractal_worker(self):
        """
        [SOVEREIGN FRACTAL v10.0] El Cerebro Central.
        Analiza 1M, 1W, 1D, 4H y 1H para todos los activos VIP.
        Sincroniza el resultado en el MemoryStore para que todos los broadcasters lo usen.
        """
        logger.info("🏛️ [ORCHESTRATOR] Fractal Intelligence Worker activado.")
        
        while not self._stop_event.is_set():
            assets = list(self.radar_assets)
            if not assets:
                await asyncio.sleep(10)
                continue
                
            for symbol in assets:
                try:
                    # 1. Obtener cierres HTF
                    tasks = [
                        fetch_binance_history(symbol, "1M", limit=50),
                        fetch_binance_history(symbol, "1w", limit=100),
                        fetch_binance_history(symbol, "1d", limit=150),
                        fetch_binance_history(symbol, "4h", limit=250),
                        fetch_binance_history(symbol, "1h", limit=250),
                    ]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    m1_raw = results[0] if not isinstance(results[0], Exception) else []
                    w1_raw = results[1] if not isinstance(results[1], Exception) else []
                    d1_raw = results[2] if not isinstance(results[2], Exception) else []
                    h4_raw = results[3] if not isinstance(results[3], Exception) else []
                    h1_raw = results[4] if not isinstance(results[4], Exception) else []
                    
                    if not d1_raw or not h4_raw or not h1_raw:
                        continue
                        
                    df_1m = pd.DataFrame([i["data"] for i in m1_raw]) if m1_raw else pd.DataFrame()
                    df_1w = pd.DataFrame([i["data"] for i in w1_raw]) if w1_raw else pd.DataFrame()
                    df_1d = pd.DataFrame([i["data"] for i in d1_raw])
                    df_h4 = pd.DataFrame([i["data"] for i in h4_raw])
                    df_h1 = pd.DataFrame([i["data"] for i in h1_raw])
                    
                    # 2. Análisis Top-Down Profesional
                    if not df_1m.empty: df_1m["timestamp"] = pd.to_datetime(df_1m["timestamp"], unit="s")
                    if not df_1w.empty: df_1w["timestamp"] = pd.to_datetime(df_1w["timestamp"], unit="s")
                    df_1d["timestamp"] = pd.to_datetime(df_1d["timestamp"], unit="s")
                    df_h4["timestamp"] = pd.to_datetime(df_h4["timestamp"], unit="s")
                    df_h1["timestamp"] = pd.to_datetime(df_h1["timestamp"], unit="s")
                    
                    bias = self.htf_analyzer.analyze_bias(df_1m, df_1w, df_1d, df_h4, df_h1)
                    
                    # 3. Persistencia en el Fractal Store
                    await store.save_htf_bias(symbol, bias)
                    
                    # 4. Actualizar Radar Global
                    await store.update_market_state(symbol, {
                        "htf_direction": bias.direction,
                        "m1_regime": bias.m1_regime,
                        "w1_regime": bias.w1_regime,
                        "d1_regime": bias.d1_regime,
                        "h4_regime": bias.h4_regime,
                        "h1_regime": bias.h1_regime
                    })
                    
                    # Pequeño delay entre activos para no saturar
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"❌ [ORCHESTRATOR] Error fractal en {symbol}: {e}")

            # Ciclo completo cada 15 min
            logger.info("🏛️ [ORCHESTRATOR] Sincronización Fractal completada.")
            await asyncio.sleep(900)

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
