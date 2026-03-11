"""
ws_manager.py — SymbolBroadcasterProxy + BroadcasterRegistry
=========================================================
Arquitectura: Gateway ultra-rápido

El Gateway NO procesa datos de mercado, NO ejecuta Pandas ni Machine Learning.
Simplemente sirve de "tubo pasante" (proxy) entre Redis Pub/Sub y el cliente WebSocket.

1. Se conecta a Redis (Upstash).
2. Lee el último estado cacheado (historial, ghost data, signals) y lo envía rápido.
3. Se suscribe al canal Pub/Sub `slingshot:stream:{symbol}:{interval}`.
4. Reparte cada mensaje a todos los clientes suscritos localmente vía asyncio.Queue.
"""

import asyncio
import json
import traceback
from typing import Dict, Optional
import uuid
import redis.asyncio as redis

from engine.api.config import settings

# Pool de Redis global (ideal usar 1 sola pool por app Uvicorn)
redis_pool = redis.from_url(settings.REDIS_URL, decode_responses=True)

class GatewayBroadcaster:
    """
    Proxy que escucha UN canal de Redis y reparte a N clientes WebSocket.
    """
    def __init__(self, symbol: str, interval: str, persistent: bool = False):
        self.symbol     = symbol.upper()
        self.interval   = interval
        self.persistent = persistent
        self._key       = f"{self.symbol}:{self.interval}"
        
        self.channel_name = f"slingshot:stream:{self.symbol}:{self.interval}"
        self.state_key    = f"slingshot:state:{self.symbol}:{self.interval}"

        self._subscribers: Dict[str, asyncio.Queue] = {}
        self._lock  = asyncio.Lock()
        self._task: Optional[asyncio.Task] = None
        self._pubsub = redis_pool.pubsub()

        print(f"[GATEWAY] ✅ Creado Proxy Broadcaster: {self._key}")

    async def start(self):
        if self._task and not self._task.done():
            return
        await self._pubsub.subscribe(self.channel_name)
        self._task = asyncio.create_task(self._run(), name=f"proxy-{self._key}")
        print(f"[GATEWAY] 📡 Escuchando canal Redis: {self.channel_name}")

    async def _run(self):
        try:
            async for message in self._pubsub.listen():
                if message["type"] == "message":
                    payload = json.loads(message["data"])
                    await self._fan_out(payload)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[GATEWAY] ⚠️ Error leyendo Redis Pub/Sub para {self._key}: {e}")
        finally:
            await self._pubsub.unsubscribe(self.channel_name)

    async def _fan_out(self, data: dict):
        """Distribuye el JSON directo de Redis a todos los web sockets."""
        dead = []
        async with self._lock:
            clients = dict(self._subscribers)
            
        for cid, q in clients.items():
            try:
                q.put_nowait(data)
            except asyncio.QueueFull:
                dead.append(cid)
                
        if dead:
            async with self._lock:
                for cid in dead:
                    self._subscribers.pop(cid, None)
                    print(f"[GATEWAY] {self._key} → cliente lento desconectado {cid[:6]}")

    async def subscribe(self, client_id: str) -> asyncio.Queue:
        """Registra un nuevo WS y le inyecta el estado cacheado en Redis."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        async with self._lock:
            self._subscribers[client_id] = queue
            count = len(self._subscribers)
        print(f"[GATEWAY] {self._key} → +cliente {client_id[:6]} (total: {count})")

        # El servidor Uvicorn hace GET a Redis (hyper rápido)
        try:
            state_json = await redis_pool.get(self.state_key)
            history_json = await redis_pool.get(f"{self.state_key}:history")

            if history_json:
                history = json.loads(history_json)
                await queue.put({"type": "history", "data": history})
            else:
                # FALLBACK REST: Si no hay un worker pesado (SMC/ML) corriendo, permitimos que el usuario al menos vea el grafico!
                print(f"[GATEWAY] ⚠️ Sin historial en Redis para {self._key}. Fallback a Binance REST.")
                try:
                    import httpx
                    url = "https://api.binance.com/api/v3/klines"
                    params = {"symbol": self.symbol, "interval": self.interval, "limit": 500}
                    async with httpx.AsyncClient() as client:
                        resp = await client.get(url, params=params)
                        if resp.status_code == 200:
                            raw = resp.json()
                            history = [
                                {"type": "candle", "data": {
                                    "timestamp": k[0] / 1000,
                                    "open": float(k[1]), "high": float(k[2]),
                                    "low": float(k[3]),  "close": float(k[4]),
                                    "volume": float(k[5]),
                                }} for k in raw
                            ]
                            await queue.put({"type": "history", "data": history})
                except Exception as e:
                    print(f"[GATEWAY] ⚠️ Error en Binance fallback: {e}")

            if state_json:
                state = json.loads(state_json)
                for key in ["ghost_update", "smc_data", "tactical_update", "session_update", "advisor_update"]:
                    val = state.get(key)
                    if val is not None:
                        # Redis state usually saves the *whole* dict (e.g. {"type": "ghost_update", "data": ...})
                        await queue.put(val)
        except Exception as e:
            print(f"[GATEWAY] ⚠️ Error sacando cache Redis para {self._key}: {e}")

        return queue

    async def unsubscribe(self, client_id: str):
        async with self._lock:
            self._subscribers.pop(client_id, None)
            count = len(self._subscribers)
        print(f"[GATEWAY] {self._key} → -cliente {client_id[:6]} (total: {count})")

    def subscriber_count(self) -> int:
        return len(self._subscribers)

    async def stop(self):
        if self._task and not self._task.done():
            self._task.cancel()
        print(f"[GATEWAY] 🛑 Detenido: {self._key}")


class BroadcasterRegistry:
    """Gestiona los Proxies que hablan con Redis o en ruta directa."""
    def __init__(self):
        self._broadcasters: Dict[str, GatewayBroadcaster] = {}
        self._lock = asyncio.Lock()
        self.orchestrator = None

    def set_orchestrator(self, orch):
        self.orchestrator = orch

    async def get_or_create(self, symbol: str, interval: str, persistent: bool = False) -> tuple[GatewayBroadcaster, str]:
        key = f"{symbol.upper()}:{interval}"
        client_id = str(uuid.uuid4())

        async with self._lock:
            if key not in self._broadcasters:
                # Dynamic On-Demand Spawn (respecting MAX_WORKERS limit in orchestrator)
                if self.orchestrator:
                    import os
                    max_w = int(os.environ.get("MAX_WORKERS", 2))
                    alive = len(self.orchestrator.get_running_keys())
                    if alive < max_w:
                        self.orchestrator._spawn_worker(symbol, interval)
                    else:
                        print(f"[GATEWAY] ⚠️ Límite de workers ({max_w}) alcanzado. Cliente verá solo gráfica REST para {symbol}.")

                broadcaster = GatewayBroadcaster(symbol, interval, persistent=persistent)
                self._broadcasters[key] = broadcaster
                await broadcaster.start()
            else:
                if persistent and not self._broadcasters[key].persistent:
                    self._broadcasters[key].persistent = True
                    
        return self._broadcasters[key], client_id

    async def release(self, symbol: str, interval: str, client_id: str):
        key = f"{symbol.upper()}:{interval}"
        async with self._lock:
            b = self._broadcasters.get(key)
            if not b: return
            
            await b.unsubscribe(client_id)
            if b.subscriber_count() == 0 and not b.persistent:
                await b.stop()
                del self._broadcasters[key]

    def status(self) -> dict:
        return {key: {"subscribers": b.subscriber_count()} for key, b in self._broadcasters.items()}

    async def broadcast_global(self, message: dict):
        """Pasa mensajes a todo el mundo que está conectado."""
        async with self._lock:
            for b in self._broadcasters.values():
                await b._fan_out(message)

registry = BroadcasterRegistry()
