"""
main.py — API Gateway Slingshot v2.0
=====================================
Responsabilidad ÚNICA: orquestación de conexiones.
Toda la lógica de análisis vive en ws_manager.SymbolBroadcaster.

Endpoints:
  GET  /                          → health check
  GET  /api/v1/status             → estado del registry (broadcasters activos)
  GET  /api/v1/analyze/{symbol}   → análisis REST one-shot (cold start)
  WS   /api/v1/stream/{symbol}    → stream en tiempo real (multi-usuario)

Tamaño objetivo: ≤200 líneas. ✅
"""
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware

from engine.api.config import settings
from engine.api.json_utils import sanitize_for_json
from engine.api.ws_manager import registry
from engine.workers.orchestrator import SlingshotOrchestrator
import asyncio

# Parchar WebSocket.send_json para usar el encoder robusto globalmente
_original_send_json = WebSocket.send_json
async def _safe_send_json(self, data, mode="text"):
    clean = sanitize_for_json(data)
    await _original_send_json(self, clean, mode=mode)
WebSocket.send_json = _safe_send_json  # type: ignore[method-assign]

global_orchestrator = SlingshotOrchestrator()

# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Slingshot v2.0 — Gateway Multi-Usuario (Compute Once, Fan-Out N)",
    version=settings.VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router one-shot para análisis REST (eliminado por arquitectura Pub/Sub)

# ── Lifespan / Startup ───────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    """Se ejecuta al arrancar el servidor. Inicia el Radar (Watchlist VIP)."""
    asyncio.create_task(global_orchestrator.start())
    print("[SLINGSHOT] 📡 Radar Center activado en segundo plano (Subprocesos independientes).")

@app.on_event("shutdown")
async def shutdown_event():
    """Se ejecuta al apagar el servidor. Cierra conexiones limpiamente."""
    global_orchestrator.stop()
    print("[SLINGSHOT] 🔌 Radar Center apagado y workers terminados.")

# ── Health & Status ───────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "status": "online",
        "engine": "Slingshot v2.0 — Compute Once, Fan-Out N",
        "version": settings.VERSION,
    }


@app.get("/api/v1/status")
async def status():
    """
    Estado del BroadcasterRegistry:
    - Cuántos símbolos tienen workers activos
    - Cuántos clientes por símbolo
    """
    return {
        "broadcasters": registry.status(),
        "total_symbols": len(registry._broadcasters),
    }


# ── REST One-Shot (Removido por arquitectura pub/sub) ─────────────────────────


# ── WebSocket Stream Multi-Usuario ───────────────────────────────────────────

@app.websocket("/api/v1/stream/{symbol}")
async def websocket_stream_endpoint(
    websocket: WebSocket,
    symbol: str,
    interval: str = Query(default="15m"),
):
    """
    Stream WebSocket multi-usuario para un símbolo dado.

    Arquitectura:
      1. El cliente se conecta → se suscribe al BroadcasterRegistry
      2. Si el broadcaster para symbol:interval no existe, se crea automáticamente
         (1 conexión Binance WS + 1 pipeline completo para ese símbolo)
      3. Si ya existe, el cliente simplemente se agrega como suscriptor
      4. El broadcaster hace fan-out de todos los mensajes via asyncio.Queue
      5. Al desconectar, si era el último cliente → el broadcaster se destruye
    """
    await websocket.accept()

    broadcaster, client_id = await registry.get_or_create(symbol, interval)
    queue = await broadcaster.subscribe(client_id)

    print(f"[GATEWAY] ✅ Cliente {client_id[:6]} conectado → {symbol.upper()}:{interval} "
          f"({broadcaster.subscriber_count()} suscriptores totales)")

    try:
        while True:
            # Espera el siguiente mensaje del broadcaster (fan-out)
            msg = await queue.get()
            await websocket.send_json(msg)

    except WebSocketDisconnect:
        print(f"[GATEWAY] Cliente {client_id[:6]} desconectado → {symbol.upper()}:{interval}")
    except Exception as e:
        print(f"[GATEWAY] Error inesperado en cliente {client_id[:6]}: {e}")
    finally:
        await registry.release(symbol, interval, client_id)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    print("[SLINGSHOT v2.0] Iniciando en http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
