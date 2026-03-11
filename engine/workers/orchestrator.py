import asyncio
from typing import List, Dict, Optional
from engine.api.ws_manager import registry
from engine.indicators.ghost_data import refresh_ghost_data, is_cache_fresh
import time

class SlingshotOrchestrator:
    """
    EL DIRECTOR DE ORQUESTA (Nivel 4).
    Responsable de mantener vivos los procesos de análisis para los activos VIP del Radar.
    Asegura que Slingshot analice y persista señales 24/7 sin depender de la UI.
    """
    
    def __init__(self, radar_assets: List[str] = None):
        # Canasta Institucional por defecto
        self.radar_assets = radar_assets or ["BTCUSDT", "ETHUSDT", "SOLUSDT", "PAXGUSDT"]
        self.intervals = ["15m", "4h"] # Vigilancia Dual-Horizon
        self._running_broadcasters = {}
        self._stop_event = asyncio.Event()

    async def start(self):
        """
        Inicia el monitoreo persistente de todos los activos del Radar en múltiples temporalidades.
        """
        print(f"📡 [ORCHESTRATOR] 🚀 Iniciando Radar Multi-Temporal (15m + 4h)...")
        
        for symbol in self.radar_assets:
            for interval in self.intervals:
                try:
                    key = f"{symbol}:{interval}"
                    broadcaster, _ = await registry.get_or_create(
                        symbol=symbol, 
                        interval=interval, 
                        persistent=True
                    )
                    self._running_broadcasters[key] = broadcaster
                    print(f"📡 [ORCHESTRATOR] ✅ Radar activo para {key}")
                    await asyncio.sleep(0.3) # Delay suave para Binance
                except Exception as e:
                    print(f"📡 [ORCHESTRATOR] ❌ Error activando radar para {symbol}:{interval}: {e}")

        print(f"📡 [ORCHESTRATOR] 🛡️  Sistema de vigilancia 24/7 desplegado con éxito.")
        
        # Mantener la tarea viva para auditoría y HEARTBEAT
        while not self._stop_event.is_set():
            await self.sync_user_watchlists() # <--- Sincronizar con lo que pidan los usuarios
            await self.audit_health()
            await self.heartbeat_ghost()      # <--- Mantener Ghost Data fresco globalmente
            await self.push_market_states()   # <--- Sincronización con UI Radar
            await asyncio.sleep(15) 

    async def sync_user_watchlists(self):
        """
        Consulta la DB para ver qué otros activos están pidiendo los usuarios 
        y los suma a la orquesta en la temporalidad base (15m).
        """
        try:
            from engine.api.supabase_client import supabase_service
            if not supabase_service: return

            response = supabase_service.table("user_watchlists").select("asset").execute()
            if response.data:
                all_watchlist_assets = {item['asset'] for item in response.data}
                
                for symbol in all_watchlist_assets:
                    # Los activos de usuario siempre se chequean mínimo en 15m
                    key = f"{symbol}:15m"
                    if key not in self._running_broadcasters:
                        print(f"📡 [ORCHESTRATOR] ✨ Nuevo activo detectado en Watchlist: {symbol}. Lanzando motor 24/7...")
                        try:
                            broadcaster, _ = await registry.get_or_create(symbol=symbol, interval="15m", persistent=True)
                            self._running_broadcasters[key] = broadcaster
                        except Exception as e:
                            print(f"📡 [ORCHESTRATOR] ❌ Error activando motor para {symbol}: {e}")
        except Exception as e:
            print(f"📡 [ORCHESTRATOR] ⚠️ Error sincronizando Watchlists: {e}")

    async def push_market_states(self):
        """
        Sube el estado de los hilos a Supabase.
        Para el Radar principal del usuario, priorizamos 15m.
        """
        states = []
        for key, b in self._running_broadcasters.items():
            # Solo enviamos al Dashboard Radar los de 15m para no saturar la UI de inicio
            if ":15m" not in key: continue 
            
            symbol = key.split(":")[0]
            state = {
                "asset": symbol,
                "price": b.latest_price or 0.0,
                "change_24h": b.change_24h,
                "regime": b._last_tactical.get("market_regime", "UNKNOWN") if b._last_tactical else "ANALIZANDO",
                "macro_bias": b._last_ghost.get("macro_bias", "NEUTRAL") if b._last_ghost else "NEUTRAL",
                "last_updated": "now()"
            }
            states.append(state)

        if not states: return

        try:
            from engine.api.supabase_client import supabase_service
            if supabase_service:
                supabase_service.table("market_states").upsert(states, on_conflict="asset").execute()
        except Exception as e:
            print(f"📡 [ORCHESTRATOR] ⚠️ Error sincronizando Radar: {e}")

    async def audit_health(self):
        """Reconexión automática de hilos caídos."""
        for key, broadcaster in list(self._running_broadcasters.items()):
            if not broadcaster._task or broadcaster._task.done():
                print(f"📡 [ORCHESTRATOR] ⚠️ {key} mudo. Reiniciando...")
                symbol, interval = key.split(":")
                await registry.get_or_create(symbol, interval, persistent=True)

    async def heartbeat_ghost(self):
        """
        Corazón macro: refresca los datos globales cada vez que expiran
        y los emite a todos los broadcasters activos.
        """
        if not is_cache_fresh("BTCUSDT"):
            print("📡 [ORCHESTRATOR] 👻 Refrescando Ghost Data Global...")
            try:
                # El orquestador solo mantiene el caché macro caliente en segundo plano.
                # Ya no emitimos globalmente para no sobrecargar de mensajes repetitivos
                # y para no 'pisar' el funding rate específico de cada activo con el de BTC.
                await refresh_ghost_data("BTCUSDT")
                print("📡 [ORCHESTRATOR] ✅ Caché Macro Global actualizado.")
            except Exception as e:
                print(f"📡 [ORCHESTRATOR] ⚠️ Error en heartbeat_ghost: {e}")

    def stop(self):
        self._stop_event.set()

# Instancia global para ser lanzada desde main.py
orchestrator = SlingshotOrchestrator()
