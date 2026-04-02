import asyncio
from typing import List, Dict, Optional
from engine.api.config import settings
from engine.api.ws_manager import registry
import engine.indicators.macro as macro
from engine.indicators.ghost_data import refresh_ghost_data, load_local_state, get_ghost_state
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
        self.intervals = ["15m"] 
        self._tasks: Dict[str, asyncio.Task] = {}
        self._stop_event = asyncio.Event()
        self.news_worker = NewsWorker()
        self.calendar_worker = CalendarWorker()

    async def start(self):
        print(f"🚀 [ORCHESTRATOR] Iniciando Motor Local Master (Modo 100% Dinámico)...")
        
        # Sincronización inicial para poblar radar_assets
        load_local_state() # Cargar datos macro previos si existen
        await self.sync_watchlists()
        
        # Iniciar Worker de Radar Macro (Ghost Data)
        asyncio.create_task(self._ghost_worker())
        # Iniciar Worker de Sesiones Globales
        asyncio.create_task(self._session_worker())
        # Iniciar Worker de Noticias en Tiempo Real
        asyncio.create_task(self.news_worker.start())
        # Iniciar Worker de Calendario Económico
        asyncio.create_task(self.calendar_worker.start())
        
        # Si la DB está vacía, podemos poner BTC por defecto para que el motor no esté ocioso
        if not self.radar_assets:
            print("ℹ️ [ORCHESTRATOR] Watchlist vacía. Usando BTCUSDT como activo de guardia.")
            await self.spawn_persistent_broadcaster("BTCUSDT", "15m")
            self.radar_assets.add("BTCUSDT")

        print(f"✅ [ORCHESTRATOR] Malla de vigilancia activa para: {self.radar_assets}")
        
        # Loop de auditoría y mantenimiento
        while not self._stop_event.is_set():
            try:
                await self.sync_watchlists()
                await self.audit_health()
            except Exception as e:
                print(f"⚠️ [ORCHESTRATOR] Error en mantenimiento: {e}")
            
            await asyncio.sleep(30) # Sincronización cada 30 segundos

    async def spawn_persistent_broadcaster(self, symbol: str, interval: str):
        """Crea un broadcaster que no se destruye aunque no haya usuarios."""
        try:
            broadcaster, client_id = await registry.get_or_create(symbol, interval, persistent=True)
            key = f"{symbol.upper()}:{interval}"
            print(f"📦 [ORCHESTRATOR] Sensor {key} garantizado en background.")
        except Exception as e:
            print(f"❌ [ORCHESTRATOR] No se pudo activar {symbol}: {e}")

    async def sync_watchlists(self):
        """
        En v3.0 (Local Master), los activos del radar se cargan 
        desde una configuración local o listado VIP hardcodeado.
        """
        vip_assets = {"BTCUSDT", "ETHUSDT", "SOLUSDT", "PAXGUSDT"}
        
        new_assets = vip_assets - self.radar_assets
        if new_assets:
            print(f"✨ [ORCHESTRATOR] Nuevos activos detectados en Watchlist VIP Local: {new_assets}")
            for sym in new_assets:
                # Disparamos fire-and-forget para no bloquear el loop principal
                asyncio.create_task(self.spawn_persistent_broadcaster(sym, "15m"))
                self.radar_assets.add(sym)

    async def audit_health(self):
        """Verifica que todos los activos VIP tengan un broadcaster activo en el registry."""
        for symbol in self.radar_assets:
            for interval in self.intervals:
                key = f"{symbol.upper()}:{interval}"
                if key not in registry._broadcasters:
                    print(f"🚨 [ORCHESTRATOR] Alerta: Sensor {key} caído. Reiniciando...")
                    await self.spawn_persistent_broadcaster(symbol, interval)

    async def _ghost_worker(self):
        """Worker secundario que refresca los datos macro globales cada 15 min."""
        print("🔮 [ORCHESTRATOR] Sensor Macro (Ghost) activado.")
        
        # Sincronización FORZADA al inicio para evitar NEUTRAL por defecto
        try:
            await macro.update_macro_context()
            m_ctx = macro.get_macro_context()
            await refresh_ghost_data("BTCUSDT", macro_ctx=m_ctx)
        except Exception as e:
            print(f"⚠️ [ORCHESTRATOR] Error en sincronización inicial: {e}")

        while not self._stop_event.is_set():
            try:
                # 1. Actualizar Capa 1: Contexto Global (DXY/NASDAQ) v4.0 PRIMERO
                await macro.update_macro_context()
                m_ctx = macro.get_macro_context()

                # 2. Refrescar datos macro (usando BTC como proxy global) DESPUÉS
                state = await refresh_ghost_data("BTCUSDT", macro_ctx=m_ctx)
                
                print(f"[ORCHESTRATOR] 🔮 Radar Macro actualizado: {state.macro_bias} (DXY: {state.dxy_trend})")
            except Exception as e:
                print(f"⚠️ [ORCHESTRATOR] Error en Radar Macro: {e}")
            
            # Esperar 15 minutos (900s) para el próximo ciclo macro
            await asyncio.sleep(900)

    async def _session_worker(self):
        """Worker que sincroniza el estado de las sesiones globales cada minuto."""
        print("🕒 [ORCHESTRATOR] Sincronizador de Sesiones Globales activo.")
        last_session = None
        
        while not self._stop_event.is_set():
            try:
                # Obtener estado global (basado en tiempo)
                status = SessionManager.get_global_session_status()
                current = status["current_session"]
                
                # Solo hacer broadcast si la sesión cambió o cada 5 minutos por seguridad
                if current != last_session:
                    print(f"[ORCHESTRATOR] 🌎 Cambio de Sesión detectado: {current}")
                    last_session = current
                    
                    # Hacer broadcast a todos los broadcasters activos
                    payload = {"type": "session_update", "data": status}
                    for broadcaster in registry._broadcasters.values():
                        await broadcaster._broadcast(payload)
                        
            except Exception as e:
                print(f"⚠️ [ORCHESTRATOR] Error en Worker de Sesiones: {e}")
            
            # Revisar cada 1 minuto (60s)
            await asyncio.sleep(60)

    def stop(self):
        """Parada coordinada."""
        self._stop_event.set()
        print("[ORCHESTRATOR] Deteniendo motor maestro...")

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
