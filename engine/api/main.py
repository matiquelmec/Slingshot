"""
main.py — API Gateway Slingshot v3.2 (Local Master)
=========================================================
Responsabilidad: Orquestación del motor local y endpoints REST/WS.
Arquitectura Zero-Redis: Todo el estado vive en engine.core.store.
"""

from engine.core.logger import logger
from pathlib import Path
from typing import Optional, List
import httpx
import pandas as pd
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware

from engine.api.config import settings
from engine.api.json_utils import sanitize_for_json, SlingshotJSONEncoder
from engine.api.registry import registry
from engine.api.ws_manager import fetch_binance_history
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
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Lifespan / Startup ───────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    """Inicialización del motor y limpieza del almacén de datos."""
    await store.clear_all() # Reset del estado efímero al arrancar
    
    # v5.9-Fix: Verificar Ollama ANTES de arrancar workers (con reintentos)
    import engine.api.advisor as advisor_module
    from engine.api.advisor import start_ai_worker
    
    # Chequeo con reintentos: Ollama puede tardar en cargar modelos en frío
    ollama_ready = False
    for attempt in range(1, 4):
        if await advisor_module.check_ollama_status(force_recheck=True):
            ollama_ready = True
            logger.info(f"🧠 [STARTUP] Ollama confirmado ONLINE (intento {attempt}/3). IA activa.")
            break
        else:
            logger.warning(f"[STARTUP] Ollama no disponible (intento {attempt}/3).")
        
        if attempt < 3:
            await asyncio.sleep(3)  # Esperar entre reintentos
    
    if not ollama_ready:
        logger.error("🚨 [STARTUP] Ollama NO disponible tras 3 intentos. Noticias sin análisis IA.")
    
    start_ai_worker()
    
    asyncio.create_task(global_orchestrator.start())

    # 🏁 Startup: Activar Radar Center para activos de Élite (Simulation)
    logger.info("[RADAR] 📡 Activando Radar Center para BTC, ETH, SOL, PAXG (Multi-TF)...")
    elite_assets = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "PAXGUSDT"]
    intervals = ["1m", "5m", "15m"]
    
    # Iniciar broadcasters persistentes para la simulación
    for asset in elite_assets:
        for interval in intervals:
            asyncio.create_task(registry.get_or_create(asset, interval, persistent=True))
    
    # Iniciar Monitor de Salud Institucional (30s Report)
    await registry.start_simulation_monitor()
    
    logger.info("[SIMULATION] 🏎️ Motores listos para el despliegue.")

@app.on_event("shutdown")
async def shutdown_event():
    """Apagado ordenado de workers."""
    global_orchestrator.stop()
    logger.info("[API] Motor Slingshot desactivado.")

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
    api_key: Optional[str] = Query(None)
):
    """
    Stream WebSocket multi-usuario para un símbolo dado.

    🔒 Sigma Security v6.0: Validación de X-API-KEY interna para evitar front-running.
    Arquitectura Delta v6.0: Utiliza el BroadcasterRegistry modularizado.
    """
    await websocket.accept()

    # 🏛️ VERIVICACIÓN DE SEGURIDAD SIGMA
    if not api_key or api_key != settings.SECURITY_API_KEY:
        logger.error(f"[GATEWAY] 🔐 Acceso denegado (Invalid API Key) a {symbol}:{interval}")
        registry.record_auth(success=False) # 📊 Registro Sigma
        await websocket.close(code=4001) # Unauthorized
        return

    registry.record_auth(success=True) # 📊 Registro Sigma
    broadcaster, client_id = await registry.get_or_create(symbol, interval)
    queue = await broadcaster.subscribe(client_id)

    logger.info(f"[GATEWAY] ✅ Acceso validado. Cliente {client_id[:6]} conectado → {symbol.upper()}:{interval} "
          f"({broadcaster.subscriber_count()} suscriptores totales)")

    try:
        while True:
            # Espera el siguiente mensaje del broadcaster (fan-out)
            msg = await queue.get()
            await websocket.send_json(msg)

    except WebSocketDisconnect:
        logger.info(f"[GATEWAY] Cliente {client_id[:6]} desconectado → {symbol.upper()}:{interval}")
    except Exception as e:
        logger.error(f"[GATEWAY] Error inesperado en cliente {client_id[:6]}: {e}")
    finally:
        await registry.release(symbol, interval, client_id)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    logger.info("[SLINGSHOT v3.2] Iniciando en http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
