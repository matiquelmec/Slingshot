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

    # 1.5 Inicializar Nodo Nexus de Ejecución Soberano
    from engine.execution.nexus import nexus
    logger.info(f"🛡️ [INIT] Nodo Nexus cargado en lifespan (Dry Run: {nexus.dry_run})")
    nexus.start_centinels()

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

from fastapi.middleware.gzip import GZipMiddleware
import time
import os

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

# Registrar tiempo de inicio para telemetría
_ENGINE_START_TIME = time.time()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Slingshot v25.3 HFT Titan (Institutional-Grade Trading Engine)",
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Compresión GZip automática para payloads > 1KB (Fast REST)
app.add_middleware(GZipMiddleware, minimum_size=1000)

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
        "engine": "Slingshot v25.3 HFT Titan",
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

@app.get("/api/v1/metrics")
async def get_metrics():
    """Telemetría de rendimiento, memoria y latencia institucional."""
    uptime_sec = time.time() - _ENGINE_START_TIME
    
    if HAS_PSUTIL:
        try:
            process = psutil.Process(os.getpid())
            mem_info = process.memory_info()
            rss_mb = round(mem_info.rss / (1024 * 1024), 2)
            vms_mb = round(mem_info.vms / (1024 * 1024), 2)
            cpu_pct = process.cpu_percent(interval=None)
        except Exception:
            rss_mb = 0.0
            vms_mb = 0.0
            cpu_pct = 0.0
    else:
        rss_mb = 0.0
        vms_mb = 0.0
        cpu_pct = 0.0
    
    return {
        "uptime_seconds": round(uptime_sec, 2),
        "uptime_formatted": f"{int(uptime_sec // 3600)}h {int((uptime_sec % 3600) // 60)}m {int(uptime_sec % 60)}s",
        "memory_rss_mb": rss_mb,
        "memory_vms_mb": vms_mb,
        "cpu_percent": cpu_pct,
        "active_broadcasters": len(registry._broadcasters),
        "stored_signals": len(await store.get_signals(limit=100)),
        "hft_latency_target_ms": "< 2.5ms"
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


@app.get("/api/v1/scanner/opportunities")
async def get_scanner_opportunities(
    category: str = Query("all", description="Filtro: scalp, swing, daily, tradfi o all")
):
    """Retorna las mejores oportunidades de corto (scalp), swing (4h), macro diario (1d) y TradFi (FTMO)."""
    cat_lower = category.lower()
    if cat_lower == "scalp":
        return {"scalp": store.get_scanner_opportunities("scalp")}
    elif cat_lower == "swing":
        return {"swing": store.get_scanner_opportunities("swing")}
    elif cat_lower == "daily":
        return {"daily": store.get_scanner_opportunities("daily")}
    elif cat_lower == "tradfi":
        return {"tradfi": store.get_scanner_opportunities("tradfi")}
    else:
        return {
            "scalp": store.get_scanner_opportunities("scalp"),
            "swing": store.get_scanner_opportunities("swing"),
            "daily": store.get_scanner_opportunities("daily"),
            "tradfi": store.get_scanner_opportunities("tradfi")
        }


@app.get("/api/v1/tradfi/opportunities")
async def get_tradfi_opportunities():
    """Retorna exclusivamente las oportunidades de trading institucional en MetaTrader 5 (FTMO)."""
    opps = store.get_scanner_opportunities("tradfi")
    return {"count": len(opps), "opportunities": opps}


@app.get("/api/v1/ftmo/guardian")
async def get_ftmo_guardian_status():
    """Retorna el estado de seguridad y telemetría de la cuenta FTMO en tiempo real."""
    from engine.risk.ftmo_guardian import ftmo_guardian
    return ftmo_guardian.update_equity(ftmo_guardian.current_equity)


@app.get("/api/v1/trades/active")
async def get_active_trades(asset: Optional[str] = Query(None)):
    """
    Retorna las señales activas con su estado de Trailing Stop Estructural.
    Incluye la fase actual (ACTIVE/BREAKEVEN/TRAILING/CLOSED),
    el SL dinámico actualizado y el historial de movimientos del trailing.
    """
    all_signals = await store.get_signals(asset=asset, status=None)
    active = [
        {
            "id":              s.get("id"),
            "asset":           s.get("asset"),
            "direction":       s.get("signal_type", "LONG"),
            "entry_price":     s.get("price"),
            "stop_loss":       s.get("stop_loss"),
            "tp1":             s.get("tp1"),
            "tp2":             s.get("tp2"),
            "tp3":             s.get("tp3", s.get("take_profit_3r")),
            "status":          s.get("status"),
            "trailing_phase":  s.get("trailing_phase", "ACTIVE"),
            "trailing_reason": s.get("trailing_reason", "SL en posicion original"),
            "trailing_history":s.get("trailing_history", []),
            "confluence":      s.get("confluence", {}).get("score", 0),
            "created_at":      s.get("created_at"),
        }
        for s in all_signals
        if s.get("status") in ("ACTIVE", "APPROVED", "BREAKEVEN", "TRAILING")
    ]
    return {"count": len(active), "trades": active}


@app.post("/api/v1/inject-test-signal")
async def inject_test_signal(
    api_key: str = Query(...),
    symbol: str = Query("BTCUSDT"),
    direction: str = Query("LONG"),
    price: float = Query(50000.0)
):
    """Inyecta una señal de prueba de forma dinámica en la instancia en ejecución de manera segura (bypassea Bitunix)."""
    from engine.api.signal_handler import SignalHandler
    from datetime import datetime, timezone

    if api_key != settings.SECURITY_API_KEY:
        raise HTTPException(status_code=401, detail="API Key inválida")

    # Si se pasa el default o 0, resolver precio real en vivo para evitar Stop Loss inmediato
    from engine.execution.bitunix_executor import BitunixExecutor
    live_executor = BitunixExecutor()
    if price == 50000.0 and symbol.upper() != "BTCUSDT":
        try:
            real_p = await live_executor.get_ticker_price(symbol.upper())
            if real_p > 0:
                price = real_p
        except Exception:
            pass

    # Garantizar distancia de respiración mínima de SL (1.8% para altcoins, 0.8% para megas)
    is_mega = any(m in symbol.upper() for m in ["BTC", "ETH", "SOL", "PAXG"])
    sl_pct = 0.008 if is_mega else 0.018

    tactical_mock = {
        "market_regime": "BULLISH_TREND" if direction.upper() == "LONG" else "BEARISH_TREND",
        "active_strategy": "SMC_APEX_SNIPER",
        "signals": [
            {
                "type": direction.upper(),
                "price": price,
                "stop_loss": price * (1.0 - sl_pct) if direction.upper() == "LONG" else price * (1.0 + sl_pct),
                "take_profit_3r": price * (1.0 + sl_pct * 3.0) if direction.upper() == "LONG" else price * (1.0 - sl_pct * 3.0),
                "tp1": price * (1.0 + sl_pct * 1.5) if direction.upper() == "LONG" else price * (1.0 - sl_pct * 1.5),
                "tp2": price * (1.0 + sl_pct * 2.5) if direction.upper() == "LONG" else price * (1.0 - sl_pct * 2.5),
                "tp3": price * (1.0 + sl_pct * 3.5) if direction.upper() == "LONG" else price * (1.0 - sl_pct * 3.5),
                "position_size": 5.0,
                "position_size_usdt": 5.0,
                "leverage": 5,
                "risk_pct": 1.0,
                "atr": price * 0.01,
                "confluence": {"score": 85},
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "is_test": True  # Flag de seguridad para evitar ejecución en broker
            }
        ],
        "smc": {
            "order_blocks": {
                "bullish": [{"bottom": price * 0.99, "top": price * 0.995}],
                "bearish": [{"bottom": price * 1.005, "top": price * 1.01}]
            }
        }
    }

    handler = SignalHandler(symbol.upper(), "15m", None)
    await handler.handle(tactical_mock)
    return {"success": True, "message": f"Test signal for {symbol.upper()} ({direction.upper()}) injected safely (No trade executed)"}



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

# ── Setup & Onboarding Router ───────────────────────────────────────────────
from engine.api.setup import router as setup_router
app.include_router(setup_router, prefix="/api/v1")

# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    logger.info(f"[SLINGSHOT v{settings.VERSION}] Iniciando en http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
