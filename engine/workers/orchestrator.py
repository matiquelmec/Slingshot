import asyncio
from typing import List, Dict, Optional
from engine.api.config import settings
from engine.api.ws_manager import registry

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

    async def start(self):
        print(f"🚀 [ORCHESTRATOR] Iniciando Motor Local Master (Modo 100% Dinámico)...")
        
        # Sincronización inicial para poblar radar_assets
        await self.sync_watchlists()
        
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
