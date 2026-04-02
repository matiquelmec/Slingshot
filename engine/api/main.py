"""
main.py — API Gateway Slingshot v3.2 (Local Master)
=========================================================
Responsabilidad: Orquestación del motor local y endpoints REST/WS.
Arquitectura Zero-Redis: Todo el estado vive en engine.core.store.
"""

from pathlib import Path
from typing import Optional, List
import httpx
import pandas as pd
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware

from engine.api.config import settings
from engine.api.json_utils import sanitize_for_json, SlingshotJSONEncoder
from engine.api.ws_manager import registry, fetch_binance_history
from engine.main_router import SlingshotRouter
from engine.core.store import store
from engine.workers.orchestrator import SlingshotOrchestrator
from engine.api.advisor import check_ollama_status
import asyncio

global_orchestrator = SlingshotOrchestrator()

# Parchar WebSocket.send_json para usar el encoder robusto globalmente
_original_send_json = WebSocket.send_json
async def _safe_send_json(self, data, mode="text"):
    clean = sanitize_for_json(data)
    await _original_send_json(self, clean, mode=mode)
WebSocket.send_json = _safe_send_json  # type: ignore[method-assign]

# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Slingshot v3.2 — Motor Local Maestro (Local-First, Zero-Latency)",
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

# ── Lifespan / Startup ───────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    """Inicialización del motor y limpieza del almacén de datos."""
    await store.clear_all() # Reset del estado efímero al arrancar
    
    # Verificar Inteligencia Local
    asyncio.create_task(check_ollama_status())
    
    asyncio.create_task(global_orchestrator.start())
    print("[API] Motor Slingshot v3.2 activado. Radar Center en línea.")

@app.on_event("shutdown")
async def shutdown_event():
    """Apagado ordenado de workers."""
    global_orchestrator.stop()
    print("[API] Motor Slingshot desactivado.")

# Router one-shot para análisis REST (no WebSocket)
_one_shot_router = SlingshotRouter()


# ── Health & Status ───────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "status": "online",
        "engine": "Slingshot v3.2 — Local Master Edition",
        "version": settings.VERSION,
    }


@app.get("/api/v1/status")
async def get_status():
    """Estado del registro de broadcasters."""
    return {
        "active_broadcasters": registry.status(),
        "total_active": len(registry._broadcasters),
    }

@app.get("/api/v1/ghost")
async def get_ghost():
    """Retorna el estado macro/ghost actual (hidratación REST para el frontend)."""
    from engine.indicators.ghost_data import get_ghost_state
    from engine.indicators.macro import get_macro_context
    from dataclasses import asdict
    ghost = get_ghost_state()
    macro = get_macro_context()
    return {
        "ghost": asdict(ghost),
        "macro": asdict(macro),
    }

@app.get("/api/v1/market-states")
async def get_market_states():
    """Retorna el estado actual de todos los activos (Radar)."""
    return await store.get_market_states()

@app.get("/api/v1/news")
async def get_news():
    """Retorna las últimas noticias analizadas."""
    return await store.get_news()

@app.get("/api/v1/calendar")
async def get_calendar():
    """Retorna el calendario económico global."""
    return await store.get_economic_events()

@app.get("/api/v1/liquidations/{asset}")
async def get_liquidations(asset: str):
    """Retorna las zonas de liquidación estimadas para un activo."""
    return await store.get_liquidation_clusters(asset)

@app.get("/api/v1/signals")
async def get_signals(
    asset: Optional[str] = Query(None),
    status: Optional[str] = Query("ALL")
):
    """Retorna el historial de señales activas o bloqueadas (Auditoría)."""
    # Si el frontend pide "ALL", pasamos None al store para no filtrar por status.
    _status_filter = None if status == "ALL" else status
    return await store.get_signals(asset=asset, status=_status_filter)


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
    print("[SLINGSHOT v3.2] Iniciando en http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
