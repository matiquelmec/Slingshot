import asyncio
import subprocess
import sys
import json
import redis.asyncio as redis
from typing import List, Dict
from engine.api.config import settings

class SlingshotOrchestrator:
    """
    EL DIRECTOR DE ORQUESTA (Nivel 4).
    Lanza los procesos (workers) usando subprocess y lee de Redis
    para subir el market_states a Supabase.
    """
    def __init__(self, radar_assets: List[str] = None):
        self.radar_assets = radar_assets or ["BTCUSDT", "ETHUSDT", "SOLUSDT", "PAXGUSDT"]
        self.intervals = ["15m"] # Por simplicidad inicial mantener 15m
        self._running_workers: Dict[str, subprocess.Popen] = {}
        self._stop_event = asyncio.Event()
        self.redis_pool = redis.from_url(settings.REDIS_URL, decode_responses=True)

    async def start(self):
        print(f"📡 [ORCHESTRATOR] 🚀 Iniciando Orquestador Multi-Proceso...")
        
        for symbol in self.radar_assets:
            for interval in self.intervals:
                self._spawn_worker(symbol, interval)

        print(f"📡 [ORCHESTRATOR] 🛡️  Sistema de vigilancia 24/7 desplegado con éxito.")
        
        while not self._stop_event.is_set():
            await self.sync_user_watchlists()
            await self.audit_health()
            await self.push_market_states()
            await asyncio.sleep(15)

    def _spawn_worker(self, symbol: str, interval: str):
        key = f"{symbol}:{interval}"
        if key in self._running_workers:
            # Check if alive
            if self._running_workers[key].poll() is None:
                return
                
        print(f"📡 [ORCHESTRATOR] ⚙️  Lanzando proceso Worker para {key}...")
        # Lanza el worker en un proceso de SO independiente, liberando a FastAPI
        proc = subprocess.Popen([sys.executable, "-m", "engine.workers.symbol_worker", symbol, "--interval", interval])
        self._running_workers[key] = proc

    async def sync_user_watchlists(self):
        try:
            from engine.api.supabase_client import supabase_service
            if not supabase_service: return

            response = supabase_service.table("user_watchlists").select("asset").execute()
            if response.data:
                all_watchlist_assets = {item['asset'] for item in response.data}
                
                for symbol in all_watchlist_assets:
                    self._spawn_worker(symbol, "15m")
        except Exception as e:
            print(f"📡 [ORCHESTRATOR] ⚠️ Error sincronizando Watchlists: {e}")

    async def push_market_states(self):
        states = []
        for key in list(self._running_workers.keys()):
            if ":15m" not in key: continue 
            symbol = key.split(":")[0]
            state_key = f"slingshot:state:{symbol}:15m"
            
            try:
                state_json = await self.redis_pool.get(state_key)
                if not state_json: continue
                state = json.loads(state_json)
                
                history = state.get("history", [])
                tactical = state.get("tactical_update", {}).get("data", {})
                ghost = state.get("ghost_update", {}).get("data", {})
                
                # Calculate change_24h basado en Redis History
                latest_price = 0.0
                change_24h = 0.0
                if history:
                    latest_price = float(history[-1].get("data", {}).get("close", 0))
                    if len(history) >= 96:
                        first_price = float(history[-96].get("data", {}).get("open", 0))
                        if first_price > 0:
                            change_24h = round(((latest_price - first_price) / first_price) * 100, 2)

                db_state = {
                    "asset": symbol,
                    "price": latest_price,
                    "change_24h": change_24h,
                    "regime": tactical.get("market_regime", "UNKNOWN") if tactical else "ANALIZANDO",
                    "macro_bias": ghost.get("macro_bias", "NEUTRAL") if ghost else "NEUTRAL",
                    "last_updated": "now()"
                }
                states.append(db_state)
            except Exception as e:
                print(f"📡 [ORCHESTRATOR] ⚠️ Error parseando Redis state para {symbol}: {e}")

        if not states: return

        try:
            from engine.api.supabase_client import supabase_service
            if supabase_service:
                supabase_service.table("market_states").upsert(states, on_conflict="asset").execute()
        except Exception as e:
            print(f"📡 [ORCHESTRATOR] ⚠️ Error sincronizando Radar en Supabase: {e}")

    async def audit_health(self):
        for key, proc in list(self._running_workers.items()):
            if proc.poll() is not None:
                print(f"📡 [ORCHESTRATOR] ⚠️ {key} DIED (Exit code {proc.returncode}). Reiniciando...")
                symbol, interval = key.split(":")
                self._spawn_worker(symbol, interval)

    def stop(self):
        self._stop_event.set()
        for key, proc in self._running_workers.items():
            print(f"📡 [ORCHESTRATOR] 🛑 Matando worker {key}...")
            proc.terminate()

async def run_orchestrator():
    orchestrator = SlingshotOrchestrator()
    try:
        await orchestrator.start()
    except KeyboardInterrupt:
        pass
    finally:
        orchestrator.stop()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_orchestrator())
