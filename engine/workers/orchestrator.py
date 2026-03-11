import asyncio
import subprocess
import sys
import json
import os
import redis.asyncio as redis
from typing import List, Dict
from engine.api.config import settings

class SlingshotOrchestrator:
    """
    EL DIRECTOR DE ORQUESTA (Nivel 4).
    Lanza los procesos (workers) en SUBPROCESS (para local/escalado) o ASYNC (para Render Free Tier),
    lee de Redis y sube states a Supabase.
    """
    def __init__(self, radar_assets: List[str] = None):
        self.worker_mode = os.environ.get("WORKER_MODE", "async") # Default to async to save RAM
        env_assets = os.environ.get("RADAR_ASSETS", "BTCUSDT")
        default_assets = [s.strip() for s in env_assets.split(",") if s.strip()]
        self.radar_assets = radar_assets or default_assets
        self.intervals = ["15m"]
        
        self._running_subprocesses: Dict[str, subprocess.Popen] = {}
        self._async_workers = {}
        self._async_tasks: Dict[str, asyncio.Task] = {}
        
        self._stop_event = asyncio.Event()
        self.redis_pool = redis.from_url(settings.REDIS_URL, decode_responses=True)

    def is_running(self, key: str) -> bool:
        if self.worker_mode == "process":
            p = self._running_subprocesses.get(key)
            return p is not None and p.poll() is None
        else:
            t = self._async_tasks.get(key)
            return t is not None and not t.done()

    def get_running_keys(self) -> List[str]:
        if self.worker_mode == "process":
            return [k for k, p in self._running_subprocesses.items() if p.poll() is None]
        else:
            return [k for k, t in self._async_tasks.items() if not t.done()]

    async def start(self):
        print(f"[ORCHESTRATOR] Iniciando Orquestador (Modo: {self.worker_mode.upper()})...")
        
        for symbol in self.radar_assets:
            for interval in self.intervals:
                self._spawn_worker(symbol, interval)

        print(f"[ORCHESTRATOR] Sistema de vigilancia 24/7 desplegado con exito.")
        
        while not self._stop_event.is_set():
            await self.sync_user_watchlists()
            await self.audit_health()
            await self.push_market_states()
            await asyncio.sleep(15)

    def _spawn_worker(self, symbol: str, interval: str):
        key = f"{symbol}:{interval}"
        if self.is_running(key):
            return
                
        print(f"[ORCHESTRATOR] Lanzando Worker para {key} (Modo: {self.worker_mode})...")
        if self.worker_mode == "process":
            proc = subprocess.Popen([sys.executable, "-m", "engine.workers.symbol_worker", symbol, "--interval", interval])
            self._running_subprocesses[key] = proc
        else:
            # Inline import para no saturar memoria si usa process mode
            from engine.workers.symbol_worker import SymbolWorker
            worker = SymbolWorker(symbol, interval, self.redis_pool)
            self._async_workers[key] = worker
            task = asyncio.create_task(worker.start(), name=f"worker-{key}")
            self._async_tasks[key] = task

    async def sync_user_watchlists(self):
        """
        Sincroniza activos de la watchlist del usuario.
        Para evitar que Render colapse, solo lanzamos workers hasta MAX_WORKERS.
        Damos prioridad a los assets en RADAR_ASSETS.
        """
        try:
            # En Render Free/Starter, MAX_WORKERS debería ser 2 o 3 máximo (BTC + PAXG + 1 extra)
            max_workers = int(os.environ.get("MAX_WORKERS", 3))
            
            from engine.api.supabase_client import supabase_service
            if not supabase_service: return

            # Obtener activos que el usuario quiere analizar
            response = supabase_service.table("user_watchlists").select("asset").execute()
            if response.data:
                all_watchlist_assets = {item['asset'] for item in response.data}
                
                # Intentar lanzar workers para la watchlist si hay espacio
                for symbol in all_watchlist_assets:
                    key = f"{symbol}:15m"
                    if not self.is_running(key) and len(self.get_running_keys()) < max_workers:
                        print(f"[ORCHESTRATOR] Activando analisis adicional para {symbol} (Respetando limite MAX_WORKERS={max_workers})")
                        self._spawn_worker(symbol, "15m")
        except Exception as e:
            print(f"[ORCHESTRATOR] Error sincronizando Watchlists: {e}")

    async def push_market_states(self):
        active_symbols = set()
        states = []
        for key in self.get_running_keys():
            if ":15m" not in key: continue 
            symbol = key.split(":")[0]
            active_symbols.add(symbol)
            
            # FILTRO CRITICO: Solo los assets de RADAR_ASSETS van al Radar Center
            if symbol not in self.radar_assets:
                continue

            state_key = f"slingshot:state:{symbol}:15m"
            try:
                state_json = await self.redis_pool.get(state_key)
                if not state_json: continue
                state = json.loads(state_json)
                history_json = await self.redis_pool.get(f"{state_key}:history")
                history = json.loads(history_json) if history_json else []
                tactical = (state.get("tactical_update") or {}).get("data", {})
                ghost = (state.get("ghost_update") or {}).get("data", {})
                
                latest_price = 0.0
                change_24h = 0.0
                if history:
                    latest_price = float(history[-1].get("data", {}).get("close", 0))
                    if len(history) >= 96:
                        first_price = float(history[-96].get("data", {}).get("open", 0))
                        if first_price > 0:
                            change_24h = round(((latest_price - first_price) / first_price) * 100, 2)

                states.append({
                    "asset": symbol,
                    "price": latest_price,
                    "change_24h": change_24h,
                    "regime": tactical.get("market_regime", "ANALIZANDO"),
                    "macro_bias": ghost.get("macro_bias", "NEUTRAL"),
                    "last_updated": "now()"
                })
            except Exception:
                pass

        # Persistencia y Limpieza de huérfanos
        try:
            from engine.api.supabase_client import supabase_service
            if supabase_service:
                if states:
                    supabase_service.table("market_states").upsert(states, on_conflict="asset").execute()
                
                # En el Radar solo queremos los oficiales
                all_db = supabase_service.table("market_states").select("asset").execute()
                if all_db.data:
                    to_delete = [row["asset"] for row in all_db.data if row["asset"] not in self.radar_assets]
                    if to_delete:
                        supabase_service.table("market_states").delete().in_("asset", to_delete).execute()
        except Exception:
            pass

    async def audit_health(self):
        if self.worker_mode == "process":
            for key, proc in list(self._running_subprocesses.items()):
                if proc.poll() is not None:
                    print(f"[ORCHESTRATOR] {key} DIED (Exit code {proc.returncode}). Reiniciando...")
                    del self._running_subprocesses[key]
                    symbol, interval = key.split(":")
                    self._spawn_worker(symbol, interval)
        else:
            for key, task in list(self._async_tasks.items()):
                if not task.done():
                    continue  # Tarea corriendo o en loop de reconexion -> OK

                # Tarea terminada: verificar si fue crash real o cancelacion limpia
                try:
                    exc = task.exception()
                    if exc:
                        print(f"[ORCHESTRATOR] {key} CRASH: {exc}. Reiniciando...")
                    else:
                        print(f"[ORCHESTRATOR] {key} termino sin excepcion. Reiniciando...")
                except asyncio.CancelledError:
                    # Cancelacion intencionada al apagar el sistema -> no relanzar
                    del self._async_tasks[key]
                    if key in self._async_workers:
                        del self._async_workers[key]
                    continue
                except Exception as e:
                    print(f"[ORCHESTRATOR] {key} error al auditar: {e}")

                del self._async_tasks[key]
                if key in self._async_workers:
                    del self._async_workers[key]
                symbol, interval = key.split(":")
                self._spawn_worker(symbol, interval)

    def stop(self):
        self._stop_event.set()
        if self.worker_mode == "process":
            for key, proc in self._running_subprocesses.items():
                print(f"[ORCHESTRATOR] Matando worker subproceso {key}...")
                proc.terminate()
        else:
            for key, task in self._async_tasks.items():
                print(f"[ORCHESTRATOR] Cancelando worker async {key}...")
                task.cancel()

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
