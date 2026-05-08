"""
main.py — API Gateway Slingshot v10.0.0 (Apex Sovereign)
=========================================================
Responsabilidad: Orquestación del motor local y endpoints REST/WS.
Arquitectura Zero-Redis: Todo el estado vive en engine.core.store.
"""

from engine.core.logger import logger
from pathlib import Path
from typing import Optional, List
import httpx
import pandas as pd
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from engine.api.config import settings
from engine.api.json_utils import sanitize_for_json, SlingshotJSONEncoder
from engine.api.registry import registry
from engine.api.ws_manager import fetch_binance_history
from engine.main_router import SlingshotRouter
from engine.core.store import store
from engine.workers.orchestrator import SlingshotOrchestrator
from engine.api.advisor import check_ollama_status, start_ai_worker
from engine.api.auth import issue_token, validate_token

# ── Global Instances ─────────────────────────────────────────────────────────

global_orchestrator = SlingshotOrchestrator()
_one_shot_router = SlingshotRouter()

# ── Patches ──────────────────────────────────────────────────────────────────

# Parchar WebSocket.send_json para usar el encoder robusto globalmente
_original_send_json = WebSocket.send_json
async def _safe_send_json(self, data, mode="text"):
    clean = sanitize_for_json(data)
    await _original_send_json(self, clean, mode=mode)
WebSocket.send_json = _safe_send_json  # type: ignore[method-assign]

# ── Lifespan Pattern (Modern FastAPI) ────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestión del ciclo de vida del motor Slingshot v10.0."""
    logger.info(f"🚀 [INIT] Slingshot v{settings.VERSION} — Iniciando...")
    
    # 1. Limpieza inicial del almacén de datos
    await store.clear_all()
    
    # 2. Inicializar Ollama (Advisor Táctico) con reintentos
    ollama_ready = False
    for attempt in range(1, 4):
        if await check_ollama_status(force_recheck=True):
            ollama_ready = True
            logger.info(f"🧠 [INIT] Ollama confirmado ONLINE (intento {attempt}/3). IA activa.")
            break
        else:
            logger.warning(f"[INIT] Ollama no disponible (intento {attempt}/3)...")
        if attempt < 3:
            await asyncio.sleep(3)
    
    if not ollama_ready:
        logger.error("🚨 [INIT] Ollama NO disponible tras 3 intentos. El sistema funcionará sin Advisor IA.")
    else:
        start_ai_worker()

    # 3. Activar el Orquestador (News, Calendar, Whale Alert)
    try:
        await global_orchestrator.start()
        logger.info("✅ [INIT] Orquestador de datos activado.")
    except Exception as e:
        logger.error(f"❌ [INIT] Error al iniciar el orquestador: {e}")

    # 4. Activar Radar Center (Health Monitor)
    logger.info(f"📡 [RADAR] Activando Radar Center para {len(settings.MASTER_WATCHLIST)} activos...")
    await registry.start_global_pulse()
    await registry.start_simulation_monitor()

    logger.info(f"🏎️  [SYSTEM] Slingshot v{settings.VERSION} listo para el despliegue.")

    yield
    
    # 🛑 Shutdown Logic
    logger.info("🛑 [SHUTDOWN] Slingshot cerrando procesos...")
    try:
        await global_orchestrator.stop()
        logger.info("✅ [SHUTDOWN] Orquestador detenido.")
    except Exception as e:
        logger.error(f"❌ [SHUTDOWN] Error al cerrar orquestador: {e}")

# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Slingshot v10.0.0 Apex Sovereign (Institutional-Grade Trading Engine)",
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Health & Status Endpoints ─────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "status": "online",
        "engine": "Slingshot v10.0.0 Apex Sovereign",
        "version": settings.VERSION,
    }

@app.get("/api/v1/health")
async def health_check():
    """Endpoint para monitoreo de salud (Docker/K8s)."""
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "ollama_active": await check_ollama_status()
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

@app.get("/api/v1/sessions/{asset}")
async def get_session_state(asset: str):
    """Retorna el estado de sesiones actual para un activo (Recovery Path)."""
    broadcaster, _ = await registry.get_or_create(asset, "15m")
    if not broadcaster:
        return {"error": "Asset not found"}
    return sanitize_for_json(broadcaster._session_manager.get_current_state())

@app.get("/api/v1/signals")
async def get_signals(
    asset: Optional[str] = Query(None),
    status: Optional[str] = Query("ALL")
):
    """Retorna el historial de señales activas o bloqueadas (Auditoría)."""
    _status_filter = None if status == "ALL" else status
    return await store.get_signals(asset=asset, status=_status_filter)


# ── REST One-Shot Analysis ────────────────────────────────────────────────────

@app.get("/api/v1/analyze/{symbol}")
async def analyze_symbol(symbol: str, timeframe: str = "15m"):
    """Análisis instantáneo de un activo sin WebSocket."""
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

@app.get("/api/v1/auth/token")
async def get_ws_token(api_key: str = Query(...)):
    """Emite un JWT para WebSocket, protegido por API Key interna."""
    if api_key != settings.SECURITY_API_KEY:
        raise HTTPException(status_code=401, detail="API Key inválida")
    
    token = issue_token()
    return {"token": token, "expires_in": 3600}

@app.websocket("/api/v1/stream/{symbol}")
async def websocket_stream_endpoint(
    websocket: WebSocket,
    symbol: str,
    interval: str = Query(default="15m"),
    token: Optional[str] = Query(None)
):
    """Stream WebSocket multi-usuario para un símbolo dado."""
    await websocket.accept()

    if not token:
        logger.error(f"[GATEWAY] 🔐 Acceso denegado (Missing Token) a {symbol}:{interval}")
        registry.record_auth(success=False)
        await websocket.close(code=4001)
        return
        
    is_valid, reason, _ = validate_token(token)
    if not is_valid:
        logger.error(f"[GATEWAY] 🔐 Acceso denegado ({reason}) a {symbol}:{interval}")
        registry.record_auth(success=False)
        await websocket.close(code=4001)
        return

    registry.record_auth(success=True)
    broadcaster, client_id = await registry.get_or_create(symbol, interval)
    queue = await broadcaster.subscribe(client_id)

    logger.info(f"[GATEWAY] ✅ Acceso validado. Cliente {client_id[:6]} conectado → {symbol.upper()}:{interval}")

    try:
        while True:
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
    logger.info(f"[SLINGSHOT v{settings.VERSION}] Iniciando en http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
