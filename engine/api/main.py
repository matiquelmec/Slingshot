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

import httpx
import pandas as pd
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware

from engine.api.config import settings
from engine.api.json_utils import sanitize_for_json, SlingshotJSONEncoder
from engine.api.ws_manager import registry, fetch_binance_history
from engine.main_router import SlingshotRouter
from engine.indicators.structure import identify_support_resistance, get_key_levels
from engine.workers.orchestrator import orchestrator
import asyncio

# Parchar WebSocket.send_json para usar el encoder robusto globalmente
_original_send_json = WebSocket.send_json
async def _safe_send_json(self, data, mode="text"):
    clean = sanitize_for_json(data)
    await _original_send_json(self, clean, mode=mode)
WebSocket.send_json = _safe_send_json  # type: ignore[method-assign]

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

# Router one-shot para análisis REST (no WebSocket)
_one_shot_router = SlingshotRouter()


# ── Lifespan / Startup ───────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    """
    Se ejecuta al arrancar el servidor. Inicia el Radar (Watchlist VIP).
    """
    # Lanzamos el orquestador en una tarea de fondo para no bloquear el arranque de la API
    asyncio.create_task(orchestrator.start())
    print("[SLINGSHOT] 📡 Radar Center activado en segundo plano.")

@app.on_event("shutdown")
async def shutdown_event():
    """
    Se ejecuta al apagar el servidor. Cierra conexiones limpiamente.
    """
    orchestrator.stop()
    print("[SLINGSHOT] 🔌 Radar Center apagado.")


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


# ── REST One-Shot ─────────────────────────────────────────────────────────────

@app.get("/api/v1/analyze/{symbol}")
async def analyze_symbol(symbol: str, timeframe: str = "15m"):
    """
    Análisis instantáneo de un activo sin WebSocket.
    Cold-start: descarga desde Binance REST si no hay datos locales.
    """
    try:
        file_path = Path(__file__).parent.parent.parent / "data" / f"{symbol.lower()}_{timeframe}.parquet"

        if not file_path.exists():
            raw = await fetch_binance_history(symbol, interval=timeframe, limit=500)
            if not raw:
                return {"error": f"Binance no devolvió datos para {symbol} en {timeframe}"}

            df = pd.DataFrame([i["data"] for i in raw])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
            file_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_parquet(file_path, index=False)
        else:
            df = pd.read_parquet(file_path)

        result = _one_shot_router.process_market_data(df, asset=symbol.upper(), interval=timeframe)
        return {"success": True, "data": sanitize_for_json(result)}

    except Exception as e:
        import traceback
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


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
