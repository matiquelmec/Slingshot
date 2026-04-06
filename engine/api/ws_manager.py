"""
ws_manager.py — SymbolBroadcaster + BroadcasterRegistry
=========================================================
Arquitectura: "Compute Once, Fan-Out N"

Un SymbolBroadcaster por símbolo activo:
  - Mantiene UNA conexión a Binance WS
  - Ejecuta el pipeline completo (SlingshotRouter) una sola vez
  - Distribuye el resultado a TODOS los clientes via asyncio.Queue

Sin importar cuántos usuarios estén viendo BTCUSDT/15m,
el pipeline se ejecuta exactamente UNA vez.

BroadcasterRegistry:
  - Crea broadcasters bajo demanda (primer usuario)
  - Los destruye automáticamente (último usuario desconecta)
  - Thread-safe via asyncio.Lock
"""

from engine.core.logger import logger
import asyncio
import json
import time
import traceback
import hashlib
from collections import deque
from datetime import datetime, timezone
from typing import Dict, Optional
import uuid

import httpx
import pandas as pd
import websockets as ws_client
from fastapi import WebSocket

from engine.api.config import settings
from engine.api.json_utils import sanitize_for_json
from engine.main_router import SlingshotRouter
from engine.core.session_manager import SessionManager
from engine.indicators.structure import (
    identify_order_blocks, extract_smc_coordinates,
    identify_support_resistance, get_key_levels, consolidate_mtf_levels,
    mitigate_smc_state, merge_smc_states
)
from engine.indicators.liquidations import estimate_liquidation_clusters
from engine.indicators.liquidity import detect_liquidity_clusters, analyze_neural_heatmap
from engine.indicators.ghost_data import (
    refresh_ghost_data, get_ghost_state, filter_signals_by_macro, 
    is_cache_fresh, fetch_funding_rate, compute_symbol_ghost
)
from engine.ml.features import FeatureEngineer
from engine.ml.inference import ml_engine
from engine.ml.drift_monitor import drift_monitor
from engine.notifications.telegram import send_signal_async
from engine.notifications.filter import signal_filter
from engine.api.advisor import generate_tactical_advice
from engine.core.store import store
from engine.indicators.htf_analyzer import HTFAnalyzer
from engine.indicators.onchain import OnChainSentinel

# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN DE ÉLITE v5.7.15 (OPERACIÓN MASTER WATCHLIST — TIERED PRIORITY)
# ──────────────────────────────────────────────────────────────────────────────
MASTER_WATCHLIST = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "PAXGUSDT"]

# 🏛️ SIGMA FIX: Tiers de Prioridad de CPU (v5.7.15 Trident Audit)
# Tier 1 (Alta Volatilidad): Cada 0.5s — Activos primarios de SMC
# Tier 2 (Media Volatilidad): Cada 1.5s — Activos secundarios
# Tier 3 (Baja Volatilidad):  Cada 5.0s — Commodities tokenizados (no gastar CPU)
PRIORITY_TIERS = {
    "BTCUSDT": 0.5,   # Tier 1
    "SOLUSDT": 0.5,   # Tier 1
    "ETHUSDT": 1.5,   # Tier 2
    "PAXGUSDT": 5.0,  # Tier 3 — Oro tokenizado, volatilidad ~0.05%
}
DEFAULT_PULSE_INTERVAL = 2.0  # Para activos fuera de la watchlist

# 🛡️ PROTECCIÓN DE OVERLOAD AI v5.7.15 (Sigma Sync)
# Limita las llamadas simultáneas a Ollama para prevenir picos de latencia masivos.
# En un VPS estándar, 1 es el máximo recomendado para Gemma-3 para evitar Drift >1000ms.
GLOBAL_AI_SEMAPHORE = asyncio.Semaphore(1)
# ──────────────────────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────────────────────
# Helpers compartidos
# ──────────────────────────────────────────────────────────────────────────────

async def fetch_binance_history(symbol: str, interval: str = "15m", limit: int = 300) -> list:
    """Descarga velas históricas desde Binance REST. Retorna lista de dicts estandarizados."""
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol.upper(), "interval": interval, "limit": limit}
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        raw = response.json()
    return [
        {"type": "candle", "data": {
            "timestamp": k[0] / 1000,
            "open": float(k[1]), "high": float(k[2]),
            "low": float(k[3]),  "close": float(k[4]),
            "volume": float(k[5]),
        }}
        for k in raw
    ]


# ──────────────────────────────────────────────────────────────────────────────
# SymbolBroadcaster — el corazón de la arquitectura
# ──────────────────────────────────────────────────────────────────────────────

class SymbolBroadcaster:
    """
    Mantiene UNA conexión Binance WS por símbolo+intervalo y distribuye
    todos los mensajes a N clientes simultáneos via asyncio.Queue.

    Ciclo de vida:
      - Se crea cuando el primer cliente se conecta
      - Se destruye cuando el último cliente desconecta
    """

    def __init__(self, symbol: str, interval: str, persistent: bool = False):
        self.symbol     = symbol.upper()
        self.interval   = interval
        self.persistent = persistent
        self._key       = f"{self.symbol}:{self.interval}"

        # Suscriptores: client_id → asyncio.Queue
        self._subscribers: Dict[str, asyncio.Queue] = {}
        self._lock  = asyncio.Lock()
        self._task: Optional[asyncio.Task] = None

        # Estado interno del broadcaster (compartido entre todas las velas)
        self._store           = store # Inyección de Élite v5.7.155 (Sigma Sync)
        self._router         = SlingshotRouter()
        self._session_manager = SessionManager(symbol=self.symbol)
        self._history: list  = []
        self._macro_levels   = None
        self._live_buffer: deque = deque(maxlen=300)
        self._last_ml        = {"direction": "CALIBRANDO", "probability": 50, "status": "warmup"}
        self._ema_ml_prob    = 50.0
        self._ml_alpha       = 0.2
        self._ml_direction   = "ANALIZANDO"
        self._candle_closes  = 0
        self._last_pulse_ts  = 0.0
        self._liquidity      = {"bids": [], "asks": []}
        self._heatmap        = {"hot_bids": [], "hot_asks": [], "imbalance": 0.0} # Neural Heatmap v5.7
        
        # ML Tracking Buffer: guarda la predicción de la vela anterior para evaluarla en el cierre (v5.7.155 Master Gold)
        self._last_ml_prediction = None

        # HTF Top-Down Analysis (v4.0)
        self._htf_analyzer = HTFAnalyzer()
        self._htf_bias     = None
        self._last_htf_ts  = 0.0        
        
        self._last_onchain_ts = 0.0 # Forza refresh inmediato
        self._last_whale_scan_ts = 0.0 # v5.7.15 DOM Scanner
        self._onchain_sentinel = OnChainSentinel(symbol=self.symbol)
        self._last_onchain = None
        self._last_onchain_ts = 0.0

        # Caché del último estado para nuevos suscriptores
        self._last_ghost     = None
        self._last_smc       = None
        self._last_tactical  = None
        self._last_session   = None
        self._last_advisor   = None
        self._last_liquidations = None
        self._persistent_smc = None
        self._first_advisor_done = False
        
        self._processed_signals_this_candle = set()
        self._last_advisor_ts = 0
        self._advisor_task: Optional[asyncio.Task] = None
        self._live_rvol: float = 0.0  # 🔴 v5.7.155 Master Gold: RVOL en tiempo real del Fast Path

        logger.info(f"[BROADCASTER] ✅ Creado: {self._key}")

    # ── Suscripción ──────────────────────────────────────────────────────────

    async def subscribe(self, client_id: str) -> asyncio.Queue:
        """Registra un nuevo cliente. Retorna su Queue personal."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        async with self._lock:
            self._subscribers[client_id] = queue
            count = len(self._subscribers)
        logger.info(f"[BROADCASTER] {self._key} → +cliente {client_id[:6]} (total: {count})")

        # Enviar historial actual y estado cacheado al nuevo cliente
        history_to_send = list(self._live_buffer) if self._live_buffer else self._history
        if history_to_send:
            await queue.put({"type": "history", "data": history_to_send})
        
        # ✅ SYNC INSTANTÁNEO: Enviar últimas señales ACTIVAS de alta calidad (v5.7.15)
        last_signals = await store.get_signals(asset=self.symbol)
        # [DELTA v5.7.15] Solo sincronizar señales que sobreviven al Filtro de Supervivencia
        for sig in list(last_signals)[-20:]:
            sig_score = sig.get("confluence", {}).get("score", 0) if sig.get("confluence") else 0
            sig_rr = sig.get("rr_ratio", 0)
            if sig.get("status") == "ACTIVE" and sig_score >= 70 and sig_rr >= 2.0:
                await queue.put({"type": "signal_auditor_update", "data": sig})

        # ✅ SYNC INSTANTÁNEO: Radar Center (Global Context)
        if registry._last_radar_summary:
            await queue.put({"type": "radar_update", "data": registry._last_radar_summary})

        if self._last_ghost:    await queue.put(self._last_ghost)
        if self._last_smc:      await queue.put(self._last_smc)
        if self._last_tactical: await queue.put(self._last_tactical)
        if self._last_session:  await queue.put(self._last_session)
        if self._last_advisor:  await queue.put(self._last_advisor)
        if self._last_liquidations: await queue.put(self._last_liquidations)
        if self._last_onchain:      await queue.put(self._last_onchain)

        return queue

    async def unsubscribe(self, client_id: str):
        """Desregistra un cliente."""
        async with self._lock:
            self._subscribers.pop(client_id, None)
            count = len(self._subscribers)
        logger.info(f"[BROADCASTER] {self._key} → -cliente {client_id[:6]} (total: {count})")

    @property
    def latest_price(self) -> float:
        """Retorna el último precio de cierre conocido."""
        if self._history:
            last = self._history[-1]
            if "data" in last:
                return float(last["data"].get("close", 0.0))
        return 0.0

    @property
    def change_24h(self) -> float:
        """
        Calcula el cambio porcentual de las últimas 24 horas.
        Para 15m, 24h = 96 velas.
        """
        if not self._history or len(self._history) < 96:
            # Fallback: si no hay suficiente historia, calculamos con lo que haya
            if len(self._history) < 2: return 0.0
            first = float(self._history[0]["data"].get("open", 0.0))
        else:
            first = float(self._history[-96]["data"].get("open", 0.0))
            
        last = self.latest_price
        if first == 0: return 0.0
        return round(((last - first) / first) * 100, 2)

    def subscriber_count(self) -> int:
        return len(self._subscribers)

    # ── Broadcast interno ────────────────────────────────────────────────────

    async def _broadcast(self, message: dict):
        """Envía un mensaje a TODOS los suscriptores activos y cachea el estado clave."""
        clean = sanitize_for_json(message)
        
        msg_type = clean.get("type", "")
        if msg_type == "ghost_update":     
            self._last_ghost = clean
            await store.update_market_state(self.symbol, {
                "macro_bias": clean["data"].get("macro_bias"),
                "dxy_trend":  clean["data"].get("dxy_trend"),
                "risk_appetite": clean["data"].get("risk_appetite")
            })
        elif msg_type == "smc_data":       
            self._last_smc = clean
            # Extraer métricas para el Radar
            data = clean.get("data", {})
            obs = data.get("order_blocks", {})
            fvgs = data.get("fvgs", {})
            await store.update_market_state(self.symbol, {
                "ob_bullish_count": len(obs.get("bullish", [])),
                "ob_bearish_count": len(obs.get("bearish", [])),
                "fvg_bullish_active": len(fvgs.get("bullish", [])) > 0,
                "fvg_bearish_active": len(fvgs.get("bearish", [])) > 0
            })
        elif msg_type == "tactical_update":
            self._last_tactical = clean
            # Extraer confluencia y riesgo macro
            data = clean.get("data", {})
            conf = data.get("confluence", {})
            await store.update_market_state(self.symbol, {
                "regime":        data.get("market_regime"),
                "strategy":      data.get("active_strategy"),
                "price":         float(data.get("current_price", 0)),
                "in_killzone":   any(f.get("factor") == "Liquidez/KZ" and f.get("status") == "CONFIRMADO" for f in conf.get("checklist", [])),
                "macro_risk":    any(f.get("factor") == "Macro Calendar" and f.get("status") == "PRECAUCIÓN" for f in conf.get("checklist", [])),
                "liq_magnet":    any(f.get("factor") == "Liq Clusters" and f.get("status") == "CONFIRMADO" for f in conf.get("checklist", []))
            })
        elif msg_type == "session_update": 
            self._last_session  = clean
            await store.update_market_state(self.symbol, {"session": clean["data"].get("current_session")})
        elif msg_type == "advisor_update":
            self._last_advisor = clean
        elif msg_type == "neural_pulse":
            data = clean.get("data", {})
            ml = data.get("ml_projection", {})
            if ml:
                await store.update_market_state(self.symbol, {
                    "ml_dir": ml.get("direction"),
                    "ml_prob": ml.get("probability")
                })
                
                # 🚀 FULL POTENTIAL: Disparar primer briefing LLM inmediato al conectar
                if not self._first_advisor_done and self._last_tactical:
                    self._first_advisor_done = True
                    asyncio.create_task(self._emit_advisor(self._last_tactical, self._last_session or {}))
        elif msg_type == "liquidation_update":
            self._last_liquidations = clean
            await store.update_liquidation_clusters(self.symbol, clean["data"])
        elif msg_type == "candle":
            await store.save_candle(self.symbol, self.interval, clean)
            await store.update_market_state(self.symbol, {"price": float(clean["data"].get("close", 0))})
        elif msg_type == "onchain_update":
            self._last_onchain = clean
        
        dead  = []
        async with self._lock:
            clients = dict(self._subscribers)
        for cid, q in clients.items():
            try:
                q.put_nowait(clean)
            except asyncio.QueueFull:
                # Cliente lento: si la queue está llena, descartamos el mensaje
                # (mejor que bloquear el broadcaster)
                dead.append(cid)
        if dead:
            async with self._lock:
                for cid in dead:
                    self._subscribers.pop(cid, None)
                    logger.info(f"[BROADCASTER] {self._key} → cliente {cid[:6]} eliminado (queue llena)")

    async def _send_to(self, client_id: str, message: dict):
        """Envía un mensaje SOLO a un cliente específico (ej: historial inicial)."""
        async with self._lock:
            q = self._subscribers.get(client_id)
        if q:
            try:
                q.put_nowait(sanitize_for_json(message))
            except asyncio.QueueFull:
                pass

    # ── Loop principal ───────────────────────────────────────────────────────

    async def start(self):
        """Inicia el loop del broadcaster en un asyncio.Task."""
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._run(), name=f"broadcaster-{self._key}")

    async def stop(self):
        """Cancela el loop y libera recursos."""
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info(f"[BROADCASTER] 🛑 Detenido: {self._key}")

    async def _run(self):
        """Loop principal: Bootstrap histórico → Stream en tiempo real."""
        retry_delay = 2.0
        while True:
            try:
                await self._bootstrap()
                await self._stream_live()
                retry_delay = 2.0  # reset en caso de éxito
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"[BROADCASTER] ⚠️ Error en {self._key}: {e}. Reintentando en {retry_delay}s...")
                traceback.print_exc()
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60.0)  # exponential backoff, máx 60s

    # ── Bootstrap (Fase 1 del stream) ────────────────────────────────────────

    async def _bootstrap(self):
        """Descarga historial inicial y envía los primeros payloads a todos los clientes."""
        logger.info(f"[BROADCASTER] {self._key} → Descargando historial desde Binance REST...")

        # 1. Historial de velas
        try:
            history = await fetch_binance_history(self.symbol, self.interval, limit=300)
            self._history = sanitize_for_json(history)
            self._live_buffer = deque(self._history[-300:], maxlen=300)
            # ✅ ZERO-TRUST INITIALIZATION: Limpiamos la caché del Advisor para forzar re-análisis
            await store.save_advisor_advice(self.symbol, {})
            logger.info(f"[BROADCASTER] {self._key} → 300 velas enviadas y caché del Advisor invalidada.")
        except Exception as e:
            logger.error(f"[BROADCASTER] {self._key} → Binance REST falló: {e}")
            history = []

        # 2. Niveles Macro MTF (1h + 4h)
        if self.interval not in ["1d", "1w"]:
            try:
                h1_raw = await fetch_binance_history(self.symbol, "1h", limit=200)
                h4_raw = await fetch_binance_history(self.symbol, "4h", limit=200)

                def _get_levels(raw, tf):
                    df = pd.DataFrame([i["data"] for i in raw])
                    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
                    df = identify_support_resistance(df, interval=tf)
                    return get_key_levels(df)

                self._macro_levels = consolidate_mtf_levels(
                    _get_levels(h1_raw, "1h"), _get_levels(h4_raw, "4h"), timeframe_weight=3
                )
                logger.info(f"[BROADCASTER] {self._key} → Niveles macro consolidados.")
            except Exception as e:
                logger.info(f"[BROADCASTER] {self._key} → MTF fallido: {e}")

        # 3. Ghost Data (Fear & Greed, BTCD, Funding específico)
        try:
            asyncio.create_task(self._refresh_ghost())
        except Exception as e:
            logger.error(f"[BROADCASTER] {self._key} → Ghost Data inicial error: {e}")

        # 3.5 HTF Bias Analysis (4H + 1H)
        try:
            await self._refresh_htf_bias()
        except Exception as e:
            logger.error(f"[BROADCASTER] {self._key} → HTF Bias inicial error: {e}")

        # 4. Bootstrap SMC + Sesiones + Pipeline inicial
        if history:
            df_init = pd.DataFrame([i["data"] for i in history])
            df_init["timestamp"] = pd.to_datetime(df_init["timestamp"], unit="s")

            # Sesiones (más rápidas — se envían primero)
            try:
                self._session_manager.bootstrap([i["data"] for i in history])
                session_state = self._session_manager.get_current_state()
                await self._broadcast(session_state)
            except Exception as e:
                logger.error(f"[BROADCASTER] {self._key} → Sesión bootstrap error: {e}")

            # Liquidaciones iniciales (Trapped Money)
            try:
                liq_clusters = estimate_liquidation_clusters(df_init, self.latest_price)
                await self._broadcast({"type": "liquidation_update", "data": liq_clusters})
            except Exception as e:
                logger.error(f"[BROADCASTER] {self._key} → Initial Liquidation error: {e}")

            # Drift Monitor — referencia inicial
            try:
                fe = FeatureEngineer()
                df_features = fe.generate_features(df_init.copy())
                drift_monitor.set_reference(df_features)
            except Exception as e:
                logger.error(f"[BROADCASTER] {self._key} → Drift reference error: {e}")

            # SMC inicial
            try:
                df_ob = identify_order_blocks(df_init)
                smc_new = extract_smc_coordinates(df_ob)
                if self._persistent_smc:
                    self._persistent_smc = merge_smc_states(
                        mitigate_smc_state(self._persistent_smc, df_ob['low'].iloc[-1], df_ob['high'].iloc[-1]),
                        smc_new
                    )
                else:
                    self._persistent_smc = smc_new
                await self._broadcast({"type": "smc_data", "data": self._persistent_smc})
            except Exception as e:
                logger.error(f"[BROADCASTER] {self._key} → SMC inicial error: {e}")

            # On-Chain inicial
            try:
                onchain_summary = await self._onchain_sentinel.refresh(
                    current_price=self.latest_price,
                    market_regime=df_init["market_regime"].iloc[-1] if "market_regime" in df_init.columns else "UNKNOWN"
                )
                await self._broadcast({"type": "onchain_update", "data": onchain_summary})
                self._last_onchain_ts = time.time()
            except Exception as e:
                logger.error(f"[BROADCASTER] {self._key} → On-Chain inicial error: {e}")

            # Pipeline táctico inicial
            try:
                self._router.set_context(session_data=self._session_manager.get_current_state().get("data", {}))
                tactical = self._router.process_market_data(
                    df_init.copy(), asset=self.symbol, interval=self.interval,
                    macro_levels=self._macro_levels,
                    htf_bias=self._htf_bias
                )
                # Inyectar último análisis cacheado para hidratación instantánea (Zero-Latency) v5.7.155 Master Gold
                if hasattr(self, '_last_advisor') and self._last_advisor:
                    tactical["advisor_log"] = self._last_advisor
                elif self.symbol:
                    # Intentar buscarlo en el store si no está en la instancia (ej: tras reinicio del registry)
                    cached = await self._store.get_advisor_advice(self.symbol)
                    if cached:
                        tactical["advisor_log"] = cached

                await self._broadcast({"type": "tactical_update", "data": tactical})
                
                # LLM Advisor inicial (no bloqueante para actualizar si es necesario)
                asyncio.create_task(self._emit_advisor(tactical, self._session_manager.get_current_state()))
            except Exception as e:
                logger.error(f"[BROADCASTER] {self._key} → Pipeline inicial error: {e}")

    # ── Stream en tiempo real (Fase 2 del stream) ────────────────────────────

    async def _stream_live(self):
        """Conexión al stream multiplexado de Binance (Spot + Futures Mark Price Check)."""
        # 1. Source Check: Futures Mark Price (v5.3 Audit)
        try:
            futures_stream_url = f"wss://fstream.binance.com/ws/{self.symbol.lower()}@markPrice"
            async with ws_client.connect(futures_stream_url, open_timeout=10) as fws:
                await fws.recv() # Wait for first frame
                logger.info(f"[SOURCE_CHECK] fapi.binance.com (Futures) CONECTADO → markPriceStream recibido.")
        except Exception as e:
            logger.warning(f"[SOURCE_CHECK] Fallo al verificar fapi.binance.com: {e}")

        kline_stream = f"{self.symbol.lower()}@kline_{self.interval}"
        depth_stream = f"{self.symbol.lower()}@depth20@100ms"
        binance_url  = f"wss://stream.binance.com:9443/stream?streams={kline_stream}/{depth_stream}"

        # 🛡️ PROTECCIÓN DE HANDSHAKE v5.7.155 Master Gold (Thundering Herd Prevention)
        # Añadimos un pequeño jitter aleatorio para no colapsar el stack de red al arrancar
        import random
        await asyncio.sleep(random.uniform(0.1, 2.0))
        
        logger.info(f"[BROADCASTER] {self._key} → Conectando a Binance WS: {binance_url}")

        # Heartbeat Robustness: Ping/Pong cada 20s y margen de 30s para el apretón de manos (handshake)
        async with ws_client.connect(
            binance_url, 
            ping_interval=20, 
            ping_timeout=20,
            open_timeout=30, # Margen extra para red saturada/VPS
            close_timeout=10
        ) as binance_ws:
            logger.info(f"[BROADCASTER] {self._key} → Stream EN VIVO 🟢")
            while True:
                raw = await asyncio.wait_for(binance_ws.recv(), timeout=30.0)
                data = json.loads(raw)
                stream_type = data.get("stream", "")
                payload_data = data.get("data", {})

                # ── Order Book Depth (Neural Heatmap v5.7) ────────────────────
                if stream_type == depth_stream:
                    price = self.latest_price or 1.0
                    self._heatmap = analyze_neural_heatmap(
                        bids=payload_data.get("bids", []),
                        asks=payload_data.get("asks", []),
                        current_price=price
                    )
                    # Mantener compatibilidad legacy para filtros básicos
                    self._liquidity = {
                        "bids": [{"price": b["price"], "volume": b["volume"]} for b in self._heatmap.get("hot_bids", [])],
                        "asks": [{"price": a["price"], "volume": a["volume"]} for a in self._heatmap.get("hot_asks", [])]
                    }
                    continue

                # ── Kline (vela) ──────────────────────────────────────────────
                if stream_type != kline_stream:
                    continue

                kline = payload_data.get("k")
                if not kline:
                    continue

                candle_payload = {
                    "type": "candle",
                    "data": {
                        "timestamp": kline["t"] / 1000,
                        "open":  float(kline["o"]),
                        "high":  float(kline["h"]),
                        "low":   float(kline["l"]),
                        "close": float(kline["c"]),
                        "volume": float(kline["v"]),
                    }
                }
                await self._broadcast(candle_payload)

                # ── Sesiones en tiempo real ───────────────────────────────────
                self._session_manager.update(candle_payload["data"])
                session_state = self._session_manager.get_current_state()
                await self._broadcast(session_state)

                # ── FAST PATH (Dinámico: Tiered Priority v5.7.15) ──────────────
                now = time.time()
                
                # --- SIGMA FIX: Tiers de Prioridad (Trident Audit) ---
                # Cada activo tiene su propio intervalo óptimo basado en volatilidad real
                is_elite = self.symbol in MASTER_WATCHLIST
                pulse_interval = PRIORITY_TIERS.get(self.symbol, DEFAULT_PULSE_INTERVAL)
                
                regime = self._last_tactical.get("data", {}).get("market_regime", "UNKNOWN") if self._last_tactical else "UNKNOWN"
                if regime in ["CHOPPY", "ACCUMULATION", "DISTRIBUTION"]:
                    pulse_interval = max(pulse_interval, 3.0)  # En rango, todos se ralentizan al mínimo de 3s
                
                if now - self._last_pulse_ts >= pulse_interval:
                    self._last_pulse_ts = now

                    # 1. Whale Sensor: [WHALE_SCAN] (v5.7.15 DOM Intelligence)
                    if now - self._last_whale_scan_ts >= 5.0: # Cada 5s
                        self._last_whale_scan_ts = now
                        try:
                            # Buscar el muro más grande en el Order Book
                            all_bids = self._liquidity.get("bids", [])
                            all_asks = self._liquidity.get("asks", [])
                            max_bid = max([float(b["volume"]) for b in all_bids]) if all_bids else 0.0
                            max_ask = max([float(a["volume"]) for a in all_asks]) if all_asks else 0.0
                            whale_size = max(max_bid, max_ask)
                            if whale_size > 0:
                                logger.info(f"[WHALE_SCAN] Order Book Muro Máximo: {whale_size:.2f} {self.symbol.replace('USDT', '')}")
                        except: pass

                    # Sincronización con Ghost Data Centralizado
                    ghost = get_ghost_state()
                    if not ghost.is_stale and (not self._last_ghost or ghost.last_updated > self._last_ghost.get("data", {}).get("last_updated", 0)):
                        await self._refresh_ghost(ghost)

                    # Refresco Periódico de HTF Bias (cada 30 min)
                    if now - self._last_htf_ts > 1800: # 30 min
                         asyncio.create_task(self._refresh_htf_bias())

                    # Refresco On-Chain (cada 30s - v5.7.15 Force Refresh)
                    if now - self._last_onchain_ts > 30: # 30s
                        try:
                            # Cálculo de SMA_20 Volumen para el Dynamic Whale Trigger (v5.3)
                            vols = [float(i["data"].get("volume", 0)) for i in list(self._live_buffer)[-20:]]
                            avg_vol_tick = (sum(vols) / len(vols)) if vols else 1.0
                            
                            # News Integration: Risk Multiplier (v5.7.15)
                            from engine.core.store import store
                            latest_news = await store.get_news(limit=1)
                            news_sentiment = latest_news[0].get("sentiment", "NEUTRAL") if latest_news else "NEUTRAL"
                            
                            onchain_summary = await self._onchain_sentinel.refresh(
                                current_price=float(kline['c']),
                                market_regime=regime,
                                avg_tick_volume=avg_vol_tick,
                                news_sentiment=news_sentiment
                            )
                            await self._broadcast({"type": "onchain_update", "data": onchain_summary})
                            self._last_onchain_ts = now
                        except Exception as e:
                            logger.error(f"[BROADCASTER] {self._key} → On-Chain refresh error: {e}")

                    current_buffer = [i["data"] for i in self._live_buffer] + [candle_payload["data"]]
                    if len(current_buffer) > 50:
                        # OMEGA FIX: Timestamps incrementales para evitar overhead de pd.to_datetime (v5.7.156 Hardening)
                        if not hasattr(self, "_cached_live_dates") or self._cached_live_dates is None:
                            base_dt = pd.to_datetime([i["data"]["timestamp"] for i in self._live_buffer], unit="s")
                            self._cached_live_dates = list(base_dt)
                        
                        new_dt = pd.Timestamp(candle_payload["data"]["timestamp"], unit="s")
                        self._cached_live_dates.append(new_dt)
                        if len(self._cached_live_dates) > 301:
                            self._cached_live_dates = self._cached_live_dates[-300:]

                        # Asincronía Total: Offload PANDAS a hilos secundarios
                        def _prepare_and_predict():
                            _df = pd.DataFrame(current_buffer)
                            _df["timestamp"] = pd.Series(self._cached_live_dates[-len(_df):])
                            return ml_engine.predict_live(_df), _df

                        loop = asyncio.get_running_loop()
                        raw_pred, df_tick = await loop.run_in_executor(None, _prepare_and_predict)
                        
                        if raw_pred.get("status") == "active":
                            raw_prob = raw_pred.get("probability", 50)
                            raw_dir  = raw_pred.get("direction", "ANALIZANDO")
                            prob_bull = raw_prob if raw_dir == "ALCISTA" else 100 - raw_prob
                            self._ema_ml_prob = (prob_bull * self._ml_alpha) + (self._ema_ml_prob * (1 - self._ml_alpha))

                            if self._ema_ml_prob >= 55.0:   self._ml_direction = "ALCISTA"
                            elif self._ema_ml_prob <= 45.0: self._ml_direction = "BAJISTA"
                            elif self._ml_direction == "ANALIZANDO": self._ml_direction = "NEUTRAL"

                            conf = self._ema_ml_prob if self._ml_direction == "ALCISTA" else (100 - self._ema_ml_prob)
                            self._last_ml = {
                                "direction": self._ml_direction,
                                "probability": int(conf),
                                "status": raw_pred["status"],
                                "reason": raw_pred["reason"]
                            }
                        else:
                            self._last_ml = raw_pred

                        # Pipeline táctico en Fast Path (SILENCIOSO v4.0)
                        try:
                            live_tactical = await asyncio.to_thread(
                                self._router.process_market_data,
                                df_tick, 
                                asset=self.symbol, 
                                interval=self.interval,
                                macro_levels=self._macro_levels,
                                htf_bias=self._htf_bias,
                                heatmap=self._heatmap, # v5.7 Neural Heatmap
                                silent=True,
                                event_time_ms=data.get("data", {}).get("E")
                            )
                            await self._broadcast({"type": "tactical_update", "data": live_tactical})

                            # 🔴 v5.7.155 Master Gold: Capturar RVOL live del Fast Path para inyectarlo al Advisor
                            fast_rvol = (live_tactical.get('diagnostic') or {}).get('rvol', 0)
                            if fast_rvol and fast_rvol > 0:
                                self._live_rvol = float(fast_rvol)
                            
                            # 🚀 HEARTBEAT DE ESCANEO: Para que el usuario vea que el motor está vivo
                            if live_tactical.get("market_regime") != "UNKNOWN":
                                # SI el análisis inicial fue N/A y ahora ya tenemos niveles, forzar actualización del Advisor
                                has_levels = len(live_tactical.get('key_levels', {}).get('supports', [])) > 0
                                if not self._first_advisor_done and has_levels:
                                    logger.info(f"[BROADCASTER] 🚀 Estructura detectada para {self.symbol}. Forzando primer análisis del Advisor...")
                                    session_state = SessionManager.get_global_session_status() # Estado actual
                                    asyncio.create_task(self._emit_advisor(live_tactical, session_state))
                                    self._first_advisor_done = True
                                    self._last_advisor_ts = live_tactical.get("timestamp", 0)

                                status_msg = f"[SCAN] Sesgo: {self._htf_bias.direction if self._htf_bias else 'NEUTRAL'} | Régimen: {live_tactical.get('market_regime')} | Filtros OK"
                                
                                # 🔴 ALERTA DE ABSORCIÓN (v5.7.15 Priority Audit)
                                # Si el RVOL llega a 3.5x, forzamos al Advisor incluso si no es cierre de vela o estamos fuera de Killzone.
                                if self._live_rvol >= 3.5:
                                    last_advisor_ts_safe = str(self._last_advisor_ts) if self._last_advisor_ts else ""
                                    current_ts = live_tactical.get("timestamp", 0)
                                    # Debouncing: No spamear el Advisor si ya lo enviamos en los últimos 2 minutos por esta alerta
                                    if str(current_ts) != last_advisor_ts_safe:
                                        logger.warning(f"[BROADCASTER] 🚨 ALERTA DE ABSORCIÓN (RVOL {self._live_rvol}x) para {self.symbol}. Prioridad Máxima.")
                                        session_state = SessionManager.get_global_session_status()
                                        asyncio.create_task(self._emit_advisor(live_tactical, session_state, is_absorption_alert=True))
                                        self._last_advisor_ts = current_ts

                                await self._broadcast({"type": "neural_log", "data": {
                                    "type": "SYSTEM",
                                    "message": status_msg
                                }})

                            # 🚀 PERSISTENCIA EN TIEMPO REAL (Fast Path - SILENCIA LOGS)
                            if live_tactical.get("signals") or live_tactical.get("blocked_signals"):
                                await self._handle_signals(live_tactical, silent=True)
                        except Exception as e:
                            logger.error(f"[BROADCASTER] {self._key} → Fast Path pipeline error: {e}")
                            traceback.print_exc()

                    # Neural Pulse
                    await self._broadcast({
                        "type": "neural_pulse",
                        "data": {
                            "ml_projection": self._last_ml,
                            "liquidity_heatmap": self._heatmap, # Enviar heatmap completo v5.7
                            "legacy_liquidity": self._liquidity,
                            "log": {
                                "type": "SENSOR",
                                "message": f"[Fast Path] Precio: ${float(kline['c']):.2f}"
                            }
                        }
                    })

                # ── SLOW PATH: cierre de vela ─────────────────────────────────
                if kline.get("x", False):
                    # Resetear debounce de señales para la nueva vela
                    self._processed_signals_this_candle.clear()
                    
                    self._live_buffer.append(candle_payload)
                    self._candle_closes += 1
                    
                    # ── Bootstrap del Slow Path (v5.7.155 Hardening) ───────────────
                    final_tactical = self._last_tactical or {}
                    session_state  = self._last_session or {}

                    df_live = pd.DataFrame([i["data"] for i in self._live_buffer])
                    df_live["timestamp"] = pd.to_datetime(df_live["timestamp"], unit="s")

                    # --- ML Accuracy Tracker para Drift Monitor (v5.7.155 Master Gold) ---
                    # Registramos el resultado de la vela que acaba de cerrar vs la predicción de la anterior.
                    if len(df_live) > 2:
                        last_c = df_live.iloc[-1]
                        actual_up = 1 if last_c['close'] > last_c['open'] else 0
                        if hasattr(self, '_last_ml_prediction') and self._last_ml_prediction:
                            pred_up = 1 if self._last_ml_prediction == "ALCISTA" else 0
                            drift_monitor.record_prediction(pred_up, actual_up)
                        
                        # Guardamos la predicción actual para evaluarla en el siguiente cierre
                        # Usamos la dirección suavizada vía EMA para evitar ruido
                        self._last_ml_prediction = self._ml_direction

                    # Drift Monitor (cada 100 velas cerradas ≈ 25h en 15m)
                    if self._candle_closes % 100 == 0:
                        asyncio.create_task(self._check_drift(df_live.copy()))
                        
                        # OMEGA FIX: Limpieza quirúrgica sin gc.collect() Stop-the-World (Trident Audit v5.7.15)
                        # En lugar de forzar GC global (congela TODOS los broadcasters),
                        # solo liberamos las referencias huérfanas que controlamos directamente.
                        self._history.clear()
                        self._cached_live_dates = None  # Se reconstruirá en el próximo tick
                        logger.info(f"[BROADCASTER] {self._key} → 🧹 Limpieza quirúrgica (sin GC global) completada.")

                    # SMC actualizado y Persistencia (Long-Term Memory V4.3)
                    try:
                        df_ob = await asyncio.to_thread(identify_order_blocks, df_live)
                        smc_new   = await asyncio.to_thread(extract_smc_coordinates, df_ob)
                        current_low = float(candle_payload["data"]["low"])
                        current_high = float(candle_payload["data"]["high"])
                        
                        if self._persistent_smc:
                            mitigated_smc = mitigate_smc_state(self._persistent_smc, current_low, current_high)
                            self._persistent_smc = merge_smc_states(mitigated_smc, smc_new)
                        else:
                            self._persistent_smc = smc_new
                            
                        await self._broadcast({"type": "smc_data", "data": self._persistent_smc})
                    except Exception as e:
                        logger.error(f"[BROADCASTER] {self._key} → SMC Slow Path error: {e}")

                    # Liquidaciones Sintéticas (Trapped Money)
                    try:
                        liq_clusters = await asyncio.to_thread(estimate_liquidation_clusters, df_live, self.latest_price)
                        await self._broadcast({"type": "liquidation_update", "data": liq_clusters})
                    except Exception as e:
                        logger.error(f"[BROADCASTER] {self._key} → Liquidation Estimator error: {e}")

                    # Pipeline táctico final (vela cerrada = máxima precisión)
                    try:
                        news_items   = await self._store.get_news()
                        econ_events  = await self._store.get_economic_events(limit=5)
                        
                        self._router.set_context(
                            ml_projection=self._last_ml,
                            session_data=session_state.get("data", {}),
                            news_items=news_items,
                            economic_events=econ_events,
                            liquidation_clusters=liq_clusters if 'liq_clusters' in locals() else []
                        )
                        final_tactical = await asyncio.to_thread(
                            self._router.process_market_data,
                            df_live, 
                            asset=self.symbol, 
                            interval=self.interval,
                            macro_levels=self._macro_levels,
                            htf_bias=self._htf_bias,
                            silent=False # En Slow Path queremos ver los porqués
                        )
                        await self._broadcast({"type": "tactical_update", "data": final_tactical})

                        # Filtro macro + Telegram + Supabase (LOGS ACTIVOS EN CIERRE)
                        await self._handle_signals(final_tactical, silent=False)

                    except Exception as e:
                        logger.error(f"[BROADCASTER] {self._key} → Slow Path pipeline error: {e}")

                    # Sesión con cierre confirmado
                    try:
                        session_state = self._session_manager.update(candle_payload["data"], is_closed=True)
                        self._last_session = session_state # Persistir en la instancia
                        await self._broadcast(session_state)
                    except Exception as e:
                        logger.error(f"[BROADCASTER] {self._key} → Session Slow Path error: {e}")

                    # 🚨 DRIFT MONITOR: Evaluación de salud del modelo ML (v5.7.155 Master Gold)
                    # Se ejecuta cada 100 velas (aprox 25h en 15m) para detectar obsolescencia.
                    if self._candle_closes % 100 == 0:
                        asyncio.create_task(self._check_drift(df_live.copy()))

                    # LLM Advisor (no bloqueante -v4.0)
                    # Solo disparamos el análisis una vez por cierre real de vela para evitar spam.
                    current_candle_ts = str(candle_payload["data"]["timestamp"])
                    last_advisor_ts_safe = str(self._last_advisor_ts) if self._last_advisor_ts else ""
                    
                    if current_candle_ts != last_advisor_ts_safe:
                        self._last_advisor_ts = current_candle_ts
                        if final_tactical and session_state:
                            asyncio.create_task(self._emit_advisor(final_tactical, session_state))
                        else:
                            logger.warning(f"[BROADCASTER] {self._key} → Advisor cancelado: Datos incompletos en Slow Path.")
                    else:
                        logger.info(f"[BROADCASTER] {self._key} → 🧠 Advisor omitido (ya analizado para esta vela)")

    async def _refresh_htf_bias(self):
        """Re-evalúa el sesgo institucional (4H + 1H) para el enrutamiento top-down."""
        try:
            h1_raw = await fetch_binance_history(self.symbol, "1h", limit=250)
            h4_raw = await fetch_binance_history(self.symbol, "4h", limit=250)
            
            df_h1 = pd.DataFrame([i["data"] for i in h1_raw])
            df_h4 = pd.DataFrame([i["data"] for i in h4_raw])
            
            df_h1["timestamp"] = pd.to_datetime(df_h1["timestamp"], unit="s")
            df_h4["timestamp"] = pd.to_datetime(df_h4["timestamp"], unit="s")
            
            self._htf_bias = self._htf_analyzer.analyze_bias(df_h4, df_h1)
            self._last_htf_ts = time.time()
            
            logger.info(f"[BROADCASTER] {self._key} → 🧭 HTF Bias Refrescado: {self._htf_bias.direction} ({self._htf_bias.reason})")
        except Exception as e:
            logger.error(f"[BROADCASTER] {self._key} → Error refrescando HTF Bias: {e}")

    # ── Handlers auxiliares ───────────────────────────────────────────────────

    async def check_ollama(self) -> bool:
        """Prueba rápida asincrónica para ver si Ollama responde en localhost:11434."""
        import httpx
        try:
            async with httpx.AsyncClient(timeout=1.0) as client:
                r = await client.get("http://localhost:11434/api/tags")
                return r.status_code == 200
        except:
            return False

    async def _handle_signals(self, tactical: dict, silent: bool = False):
        """Filtra por macro, notifica por Telegram y persiste en MemoryStore local (v3.0).
        En Audit Mode: también persiste las señales RECHAZADAS por el Portero Institucional o HTF.
        """
        raw_signals = tactical.get("signals", [])
        router_blocked = tactical.get("blocked_signals", [])

        # Si no hay nada en absoluto, salir
        if not raw_signals and not router_blocked:
            return

        # --- DEBOUNCE INSTITUCIONAL (v4.0) ---
        # Identificar señales únicas para evitar spam en el Fast Path (mismo candle).
        # Generamos un ID basado en Asset, Tipo, Score y Timestamp de la vela.
        def get_sig_id(s):
            ts = s.get("timestamp") or s.get("time") or tactical.get("candles", [{}])[-1].get("timestamp", 0)
            score = s.get("confluence", {}).get("total_score", 0)
            return f"{self.symbol}:{s.get('type', 'LONG')}:{ts}:{score}"

        unique_new = []
        for s in raw_signals:
            sid = get_sig_id(s)
            if sid not in self._processed_signals_this_candle:
                unique_new.append(s)
                self._processed_signals_this_candle.add(sid)

        unique_blocked = []
        for s in router_blocked:
            sid = get_sig_id(s)
            if sid not in self._processed_signals_this_candle:
                unique_blocked.append(s)
                self._processed_signals_this_candle.add(sid)

        if not unique_new and not unique_blocked:
            return # Ya hemos auditado estas señales en este ciclo de vela

        ghost = get_ghost_state()
        approved, macro_blocked = filter_signals_by_macro(unique_new, ghost)
        
        # ──────── PROCESAR APROBADAS Y TELEGRAM ────────
        final_approved = []
        for sig in approved:
            # Telegram (Filtro Anti-Spam / Cooldown)
            ok_to_send, reason = signal_filter.should_send(self.symbol, sig)
            if ok_to_send:
                asyncio.create_task(send_signal_async(
                    signal=sig, asset=self.symbol,
                    regime=tactical.get("market_regime", "UNKNOWN"),
                    strategy=tactical.get("active_strategy", "N/A")
                ))
                final_approved.append(sig)
            else:
                logger.info(f"[BROADCASTER] {self._key} → 🔕 Telegram bloqueado: {reason}")
                sig["blocked_reason"] = reason
                macro_blocked.append(sig)
        
        # ──────── PERSISTIR ACTIVAS ────────
        for sig in final_approved:
            asyncio.create_task(self._persist_signal(sig, tactical, status="ACTIVE", silent=silent))

        # ──────── [DELTA v5.7.15] SEÑALES BLOQUEADAS: SOLO LOG INTERNO, CERO UI ────────
        # Macro-blocked y router-blocked se registran en logs del servidor,
        # pero NUNCA se envían al Dashboard. Limpieza visual absoluta.
        for sig in macro_blocked:
            motivo = sig.get("blocked_reason", "Bloqueada por filtro macro")
            if not silent:
                logger.info(f"[GATEKEEPER] 🔇 Señal macro-bloqueada ({self.symbol}): {motivo}")

        for sig in unique_blocked:
            motivo = sig.get("blocked_reason", "Rechazada por filtro táctico")
            if not silent:
                logger.info(f"[GATEKEEPER] 🔇 Señal router-bloqueada ({self.symbol}): {motivo}")

    async def _check_drift(self, df_live: pd.DataFrame):
        """
        Analiza si el mercado ha divergido de los datos de entrenamiento (Population Stability Index).
        Si detecta drift severo, emite una alerta institucional a Telegram.
        """
        try:
            logger.info(f"[BROADCASTER] 🔍 Ejecutando Drift Monitor para {self.symbol}...")
            
            # --- 0. Generar features para el análisis de distribución ---
            # El monitor espera features procesadas (RSI, MACD, etc), no Ohlcv crudo.
            fe = FeatureEngineer()
            df_features = fe.generate_features(df_live.copy())

            # --- 1. Evaluar Drift via PSI ---
            # El monitor ya tiene el historial de accuracy actualizado del Slow Path.
            report = drift_monitor.check(df_features)
            
            if not report:
                return

            # --- 3. Si hay alerta disparada, notificar vía Telegram ---
            if report.alert_triggered:
                from engine.notifications.telegram import send_drift_alert_async
                
                drift_payload = {
                    "asset": self.symbol,
                    "affected_features": ", ".join(report.features_in_drift) if report.features_in_drift else "Generales",
                    "rolling_accuracy": f"{report.rolling_accuracy * 100:.1f}",
                    "psi_max": f"{report.psi_max:.3f}",
                    "level": report.drift_level,
                    "recommendation": report.recommendation
                }
                
                await send_drift_alert_async(drift_payload)
                
                # Log en la consola institucional (Frontend)
                await self._broadcast({
                    "type": "neural_log", 
                    "data": {
                        "type": "WARNING",
                        "message": f"🚨 {self.symbol} DRIFT MONITOR: {report.recommendation}"
                    }
                })
            else:
                logger.info(f"[BROADCASTER] ✅ Drift Monitor ({self.symbol}): Modelo estable (PSI Max: {report.psi_max:.3f})")

        except Exception as e:
            import traceback
            logger.error(f"[BROADCASTER] ❌ Error en Drift Monitor ({self.symbol}): {e}")
            traceback.print_exc()
            traceback.print_exc()



    async def _persist_signal(self, sig: dict, tactical: dict, status: str = "ACTIVE", rejection_reason: str = None, silent: bool = False):
        """Inserta la señal en public.signal_events y en el MemoryStore local."""
        ghost = get_ghost_state()
        
        # Mantener identidad de la señal: Si ya trae un timestamp (de la vela), usarlo. 
        # Si no, usar la última vela de tactical.
        raw_ts = sig.get("timestamp") or sig.get("time")
        if not raw_ts and "candles" in tactical: # Fallback a última vela
            raw_ts = tactical["candles"][-1]["timestamp"] if tactical["candles"] else None
        
        final_ts = raw_ts if raw_ts else datetime.now(timezone.utc).isoformat()
        if isinstance(final_ts, (int, float)):
            final_ts = datetime.fromtimestamp(final_ts, tz=timezone.utc).isoformat()

        # --- CÁLCULO DE RIESGO HIPOTÉTICO (Audit Mode) ---
        # Si la señal no trae cálculos de riesgo (posible en señales rechazadas), los simulamos.
        risk_pct = sig.get("risk_pct")
        risk_usd = sig.get("risk_amount_usdt", sig.get("risk_usd"))
        pos_size = sig.get("position_size_usdt", sig.get("position_size"))
        lev      = sig.get("leverage", 1)

        if not risk_pct or not pos_size:
            try:
                from engine.risk.risk_manager import RiskManager
                # Instanciamos el RiskManager con el balance actual del Ghost State
                rm = RiskManager(account_balance=float(ghost.get("total_balance", 1000.0)))
                
                # Simulamos el cálculo estructural para que la UI no muestre N/A
                calc = rm.calculate_position(
                    current_price=float(sig.get("price", 0)),
                    signal_type=sig.get("signal_type", sig.get("type", "LONG")).upper(),
                    market_regime=tactical.get("market_regime", "UNKNOWN"),
                    smc_data=tactical.get("smc"),
                    atr_value=sig.get("atr", 0)
                )
                risk_pct = calc.get("risk_pct")
                risk_usd = calc.get("risk_amount_usdt")
                pos_size = calc.get("position_size_usdt")
                lev      = calc.get("leverage")
            except Exception as e:
                logger.error(f"[AUDITOR] Error simulando riesgo: {e}")

        realtime_data = {
            "asset":            self.symbol,
            "interval":         self.interval,
            "signal_type":      sig.get("signal_type", sig.get("type", "LONG")).upper(),
            "type":             sig.get("signal_type", sig.get("type", "LONG")).upper(),
            "entry_price":      float(sig.get("price", 0)),
            "price":            float(sig.get("price", 0)),
            "stop_loss":        float(sig.get("stop_loss", 0)),
            "take_profit_3r":   float(sig.get("take_profit_3r", 0)),
            "confluence_score": float(sig.get("confluence", {}).get("total_score", 0)) if sig.get("confluence") else 0,
            "regime":           tactical.get("market_regime", "UNKNOWN"),
            "strategy":         tactical.get("active_strategy", "N/A"),
            "trigger":          sig.get("trigger", "N/A"),
            "status":           status,
            "rejection_reason": rejection_reason,
            "timestamp":        final_ts,
            "confluence":       sig.get("confluence"),
            "risk_pct":         risk_pct,
            "risk_usd":         risk_usd,
            "position_size":    pos_size,
            "leverage":         lev,
            "rr_ratio":         round(abs(float(sig.get("take_profit_3r", 0)) - float(sig.get("price", 0))) / abs(float(sig.get("price", 0)) - float(sig.get("stop_loss", 0.001))) if abs(float(sig.get("price", 0)) - float(sig.get("stop_loss", 0))) > 0 else 0, 2)
        }
        
        # Persistencia en Memoria Local (siempre, para logs internos)
        asyncio.create_task(self._store.save_signal(realtime_data))
        
        # [DELTA v5.7.15] Solo emitir al Dashboard si la señal es ACTIVA y de alta calidad
        # Señales FILTER/SILENCE/BLOCKED se quedan en logs del servidor, fuera de la UI.
        sig_score = realtime_data.get("confluence", {}).get("score", 0) if realtime_data.get("confluence") else 0
        if status == "ACTIVE" and sig_score >= 70 and realtime_data.get("rr_ratio", 0) >= 2.0:
            await self._broadcast({"type": "signal_auditor_update", "data": realtime_data})
        
        # En v3.0, solo guardamos en memoria. Print de confirmación local.
        icon = "✅" if status == "ACTIVE" else "🚫"
        if not silent:
            logger.info(f"[LOCAL STORE] {icon} Señal ({status}) persistida: {realtime_data['signal_type']} {self.symbol} @ ${realtime_data['entry_price']:.2f}")

    def _get_tactical_hash(self, tactical: dict) -> str:
        """Genera un hash MD5 del estado táctico (excluyendo datos volátiles)."""
        # Extraemos solo lo estructural para el caché semántico
        stable_keys = {
            "market_regime", "active_strategy", "macro_bias", 
            "htf_bias", "smc", "diagnostic", "key_levels"
        }
        state = {k: v for k, v in tactical.items() if k in stable_keys}
        
        # Redondear niveles de Fibonacci y OBs para evitar invalidación por micro-pips
        # (Opcional, pero ayuda al hit-rate del caché)
        
        state_str = json.dumps(state, sort_keys=True, default=str)
        return hashlib.md5(state_str.encode()).hexdigest()

    async def _emit_advisor(self, tactical: dict, session_state: dict, is_absorption_alert: bool = False):
        """Llama al LLM Advisor y broadcast el resultado (v5.7.155 Master Gold Live Price Injection)."""
        
        # 🔴 FIX CRÍTICO v5.7.155 Master Gold: Inyectar datos LIVE antes de enviar al LLM
        # El tactical dict fue capturado como snapshot en el momento del cierre de vela.
        # Si Ollama tarda 30-60s, el precio puede haber movido $500-$900.
        live_overrides = {}
        if self.latest_price and self.latest_price > 0:
            live_overrides["current_price"] = self.latest_price
        
        # 🔴 FIX RVOL v5.7.155 Master Gold: El RVOL del Slow Path es de la vela CERRADA (ej: 0.15x).
        # El RVOL del Fast Path es de la vela EN FORMACIÓN (ej: 33.36x).
        # El Advisor debe ver el RVOL más alto de ambos para detectar Absorción Institucional.
        if self._live_rvol > 0:
            slow_rvol = (tactical.get('diagnostic') or {}).get('rvol', 0)
            max_rvol = max(float(slow_rvol), self._live_rvol)
            diag_copy = dict(tactical.get('diagnostic') or {})
            diag_copy['rvol'] = round(max_rvol, 2)
            live_overrides["diagnostic"] = diag_copy
        
        if live_overrides:
            tactical = {**tactical, **live_overrides}
        
        # ✅ VERIFICACIÓN DE CACHÉ INTERNO (SMC v5.7.155 Master Gold)
        # Si ya tenemos un análisis para esta vela en el Store, lo reutilizamos.
        current_candle_ts = tactical.get("candles", [{}])[-1].get("timestamp", 0) if tactical.get("candles") else 0
        
        # Si ya existe un análisis para este activo en el store, no volvemos a llamar a Ollama.
        # EXCEPCIÓN: Si el análisis guardado es un error (trae N/A o estructura no identificada), lo ignoramos.
        existing_advice = await self._store.get_advisor_advice(self.symbol)
        if existing_advice and existing_advice.get("timestamp") == current_candle_ts:
            content = existing_advice.get("content", "")
            if "N/A" not in content and "ESTRUCTURA NO IDENTIFICADA" not in content:
                logger.info(f"[BROADCASTER] ♻️ Reutilizando análisis cacheado para {self.symbol} ({current_candle_ts})")
                self._last_advisor = existing_advice
                await self._broadcast({"type": "advisor_update", "data": existing_advice})
                return
            else:
                logger.info(f"[BROADCASTER] 🔃 Re-generando análisis para {self.symbol} (Caché previo era inválido/incompleto)")

        # ✅ VERIFICACIÓN PREVENTIVA (Ollama) v5.7.155 Master Gold
        # Si el motor IA no responde rápido, informamos al usuario de inmediato en vez de colgar el sistema.
        if not await self.check_ollama():
            logger.info(f"[BROADCASTER] ⚠️ Ollama no disponible para {self.symbol}")
            await self._broadcast({"type": "advisor_update", "data": {
                "content": "⚠️ MOTOR IA OFFLINE: El motor Ollama no responde en localhost:11434. Asegúrate de que Ollama esté abierto.",
                "timestamp": current_candle_ts,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }})
            return

        # ✅ CACHÉ SEMÁNTICO MD5 (v5.4 Optimization)
        # Si la estructura no ha mutado, reutilizamos el consejo para ahorrar CPU (Gemma-3).
        tactical_hash = self._get_tactical_hash(tactical)
        
        # Bypasseamos el caché si es una ALERTA DE ABSORCIÓN crítica
        cache_hit = hasattr(self, '_last_tactical_hash') and self._last_tactical_hash == tactical_hash
        
        if cache_hit and not is_absorption_alert:
            logger.info(f"[BROADCASTER] 🧠 Cache Semántico HIT para {self.symbol}. Contexto idéntico.")
            if self._last_advisor:
                await self._broadcast({"type": "advisor_update", "data": self._last_advisor})
                return

        self._last_tactical_hash = tactical_hash

        if is_absorption_alert:
            logger.info(f"[BROADCASTER] 🧪 Inyectando Etiqueta de ABSORCIÓN INSTITUCIONAL en el payload...")
            tactical["alert_type"] = "ALERTA DE ABSORCIÓN"
            tactical["priority"] = "MAXIMA"

        logger.info(f"[BROADCASTER] 🧠 Iniciando análisis LLM para {self.symbol}...")
        
        # ✅ CANCELACIÓN DE TAREA PREVIA (Inteligencia de Concurrencia)
        # Si ya hay un análisis corriendo (ej: cambio rápido de moneda), lo cancelamos para liberar el semáforo
        if self._advisor_task and not self._advisor_task.done():
            self._advisor_task.cancel()
            logger.info(f"[BROADCASTER] 🔃 Análisis previo cancelado para {self.symbol} (Nueva petición)")

        try:
            loading_obj = {
                "content": "CONECTANDO CON EL MOTOR CUÁNTICO (Ollama)... ⚡",
                "timestamp": current_candle_ts,
                "status": "LOADING_IA",
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            # self._last_advisor se actualizará automáticamente via _broadcast
            await self._broadcast({"type": "advisor_update", "data": loading_obj})

            # Creamos la tarea para poder cancelarla si fuera necesario
            self._advisor_task = asyncio.current_task()

            # Obtener datos adicionales del store para el LLM
            news_items = await self._store.get_news(limit=5)
            liqs = await self._store.get_liquidation_clusters(self.symbol)
            econ_events = await self._store.get_economic_events(limit=5)

            # ✅ SERIALIZACIÓN ROBUSTA (v5.7.155 Master Gold)
            # Convertimos tipos de Numpy a Python nativo (Evita el bug del N/A)
            import numpy as np
            def sanitize(obj):
                if isinstance(obj, dict):
                    return {k: sanitize(v) for k, v in obj.items()}
                if isinstance(obj, list):
                    return [sanitize(i) for i in obj]
                if isinstance(obj, (np.float64, np.float32)):
                    return float(obj)
                if isinstance(obj, (np.int64, np.int32)):
                    return int(obj)
                return obj

            payload = tactical.copy()
            payload.pop("candles", None)
            sanitized_tactical = sanitize(payload)

            # Timeout de 45 segundos para VPS — liberar recursos si la IA no responde
            # 🛡️ Uso del Semáforo Global para prevenir Drift por saturación de CPU/GPU (v5.7.155)
            async with GLOBAL_AI_SEMAPHORE:
                advice = await asyncio.wait_for(
                    generate_tactical_advice(self.symbol, 
                        tactical_data=sanitized_tactical,
                        current_session=session_state.get("data", {}).get("current_session", "UNKNOWN"),
                        ml_projection=self._last_ml,
                        news=news_items,
                        liquidations=liqs,
                        economic_events=econ_events,
                        onchain_data=self._last_onchain.get("data") if self._last_onchain else None
                    ),
                    timeout=45.0
                ) 
            logger.info(f"[BROADCASTER] ✅ Análisis LLM completado para {self.symbol}")
            
            # ✅ PERSISTENCIA EN EL STORE (v5.7.155 Master Gold)
            # Guardamos el análisis con el timestamp de la vela para el debouncing global
            advice_obj = {
                "timestamp": current_candle_ts,
                "asset": self.symbol,
                "content": advice,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            await self._store.save_advisor_advice(self.symbol, advice_obj)
            
            # self._last_advisor será actualizado por _broadcast
            await self._broadcast({"type": "advisor_update", "data": advice_obj})
        except asyncio.TimeoutError:
            logger.info(f"[BROADCASTER] ⚠️ Timeout en LLM Advisor ({self.symbol})")
            error_obj = {
                "content": "⚠️ MOTOR IA SATURADO: Ollama está tardando demasiado en responder. Reintentando en la próxima vela...",
                "timestamp": current_candle_ts,
                "status": "TIMEOUT",
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            self._last_advisor = error_obj
            await self._broadcast({"type": "advisor_update", "data": error_obj})
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[BROADCASTER] ❌ {self._key} → Advisor error: {e}")
            await self._broadcast({"type": "advisor_update", "data": {
                "content": f"ADVISOR OFFLINE: {str(e)}",
                "timestamp": current_candle_ts,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }})
            traceback.print_exc()

    async def _refresh_ghost(self, global_ghost=None):
        """Refresca Ghost Data (Funding específico + Global context) y broadcast."""
        try:
            # 1. Obtener contexto global (F&G, Dominancia)
            if not global_ghost:
                global_ghost = get_ghost_state()
            
            # 2. Obtener Funding específico de este símbolo en tiempo real
            local_funding = await fetch_funding_rate(self.symbol)
            
            # 3. Calcular Bias híbrido
            ghost = compute_symbol_ghost(global_ghost, self.symbol, local_funding)
            
            # 4. 🔴 SESGO UNIFICADO v5.7.155 Master Gold (Conflict Resolution)
            # Reconcilia Macro (Ghost) + Estructura (SMC/Wyckoff) + ML en un veredicto único.
            # Si hay contradicción → STAND_BY. Evita que el frontend muestre señales conflictivas.
            ml_dir = (self._last_ml or {}).get("direction", "NEUTRAL")
            ml_dir_normalized = "BULLISH" if ml_dir == "ALCISTA" else ("BEARISH" if ml_dir == "BAJISTA" else "NEUTRAL")
            
            macro_dir = ghost.macro_bias  # BULLISH / BEARISH / BLOCK_LONGS / BLOCK_SHORTS / NEUTRAL
            macro_bullish = macro_dir in ("BULLISH", "BLOCK_SHORTS")
            macro_bearish = macro_dir in ("BEARISH", "BLOCK_LONGS")
            
            ml_bullish = ml_dir_normalized == "BULLISH"
            ml_bearish = ml_dir_normalized == "BEARISH"
            
            if macro_bullish and ml_bullish:
                system_verdict = "BULLISH"
            elif macro_bearish and ml_bearish:
                system_verdict = "BEARISH"
            elif (macro_bullish and ml_bearish) or (macro_bearish and ml_bullish):
                system_verdict = "STAND_BY"
            else:
                system_verdict = "NEUTRAL"
            
            # 5. Broadcast
            await self._broadcast({"type": "ghost_update", "data": {
                "symbol":           self.symbol,
                "fear_greed_value": ghost.fear_greed_value,
                "fear_greed_label": ghost.fear_greed_label,
                "btc_dominance":    ghost.btc_dominance,
                "funding_rate":     ghost.funding_rate,
                "funding_symbol":   ghost.funding_symbol,
                "macro_bias":       ghost.macro_bias,
                "block_longs":      ghost.block_longs,
                "block_shorts":     ghost.block_shorts,
                "reason":           ghost.reason,
                "last_updated":     ghost.last_updated,
                "dxy_trend":        ghost.dxy_trend,
                "dxy_price":        ghost.dxy_price,
                "nasdaq_trend":     ghost.nasdaq_trend,
                "nasdaq_change_pct":ghost.nasdaq_change_pct,
                "risk_appetite":    ghost.risk_appetite,
                "system_verdict":   system_verdict,
            }})
        except Exception as e:
            logger.error(f"[BROADCASTER] {self._key} → Ghost specific refresh error: {e}")

    async def _check_drift(self, df: pd.DataFrame):
        """Ejecuta el drift monitor y broadcast alerta si hay drift."""
        try:
            fe = FeatureEngineer()
            # Asincronía: Offload CPU-heavy pipeline out of main event loop
            df_features = await asyncio.to_thread(fe.generate_features, df)
            report = await asyncio.to_thread(drift_monitor.check, df_features)
            if report and report.alert_triggered:
                await self._broadcast({"type": "drift_alert", "data": report.to_dict()})
        except Exception as e:
            logger.error(f"[BROADCASTER] {self._key} → Drift check error: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# BroadcasterRegistry — gestiona el ciclo de vida de todos los broadcasters
# ──────────────────────────────────────────────────────────────────────────────

class BroadcasterRegistry:
    """
    Registro global de SymbolBroadcasters.
    Crea un broadcaster cuando el primer cliente se conecta a un símbolo.
    Lo destruye cuando el último cliente desconecta.
    """

    def __init__(self):
        self._broadcasters: Dict[str, SymbolBroadcaster] = {}
        self._lock = asyncio.Lock()
        self._pulse_task: Optional[asyncio.Task] = None
        self._last_radar_summary: Optional[list] = None

    async def start_global_pulse(self):
        """Inicia el latido global que sincroniza el estado de todos los radares."""
        if self._pulse_task: return
        self._pulse_task = asyncio.create_task(self._pulse_loop())
        logger.info("[REGISTRY] 💓 Global Radar Pulse iniciado (3s interval)")

    async def _pulse_loop(self):
        """Loop que emite el estado resumido de todo el mercado cada 3 segundos."""
        while True:
            try:
                await asyncio.sleep(3) # Optimizado a 3s para feed institucional
                # 1. Obtener estados de todos los activos desde el store
                states = await store.get_market_states()
                if not states: continue

                # 2. Simplificar para el Radar (ahorro de ancho de banda)
                summary = []
                for s in states:
                    summary.append({
                        "asset":       s.get("asset"),
                        "price":       s.get("price") or s.get("current_price"),
                        "regime":      s.get("regime") or s.get("market_regime", "UNKNOWN"),
                        "strategy":    s.get("strategy") or "SMC INSTITUTIONAL",
                        "bias":        s.get("macro_bias") or (s.get("htf_bias", {}).get("direction", "NEUTRAL") if isinstance(s.get("htf_bias"), dict) else "NEUTRAL"),
                        "ob_count":    (s.get("ob_bullish_count", 0) + s.get("ob_bearish_count", 0)),
                        "fvg_active":  (s.get("fvg_bullish_active", False) or s.get("fvg_bearish_active", False)),
                        "is_killzone": s.get("in_killzone", False),
                        "macro_risk":  s.get("macro_risk", False),
                        "liq_magnet":  s.get("liq_magnet", False),
                        "ml_dir":      s.get("ml_dir", "NEUTRAL"),
                        "ml_prob":     s.get("ml_prob", 50),
                        "sentiment":   s.get("risk_appetite", "NEUTRAL")
                    })

                self._last_radar_summary = summary

                # 3. Fan-out: Enviar a TODOS los broadcasters activos
                async with self._lock:
                    for b in self._broadcasters.values():
                        await b._broadcast({"type": "radar_update", "data": summary})
            except Exception as e:
                logger.error(f"[REGISTRY] Pulse error: {e}")
                await asyncio.sleep(5)

    async def get_or_create(self, symbol: str, interval: str, persistent: bool = False) -> tuple[SymbolBroadcaster, str]:
        """
        Retorna el broadcaster para symbol:interval, creándolo si no existe.
        También retorna el client_id único para este suscriptor.
        """
        # Asegurarse de que el pulso global esté corriendo
        if not self._pulse_task:
            await self.start_global_pulse()

        key = f"{symbol.upper()}:{interval}"
        client_id = str(uuid.uuid4())

        async with self._lock:
            if key not in self._broadcasters:
                # ── PROTOCOLO CROSS-PAIR SAFETY v5.7.155 Master Gold ──
                # Antes de arrancar el broadcaster, limpiamos basura de sesiones previas en el Store
                # para este activo, garantizando que el análisis empiece de cero (Flush & Sync).
                await store.flush_symbol(symbol.upper())

                broadcaster = SymbolBroadcaster(symbol, interval, persistent=persistent)
                self._broadcasters[key] = broadcaster
                await broadcaster.start()
                logger.info(f"[REGISTRY] ✅ Nuevo broadcaster: {key}")
            else:
                # Si ya existía pero no era persistente y ahora se pide persistencia (ej: por orquestador)
                if persistent and not self._broadcasters[key].persistent:
                    self._broadcasters[key].persistent = True
                    logger.info(f"[REGISTRY] 💎 Broadcaster {key} elevado a PERSISTENTE")
                    
                logger.info(f"[REGISTRY] ♻️  Reutilizando broadcaster: {key} ({self._broadcasters[key].subscriber_count()} clientes activos)")

        return self._broadcasters[key], client_id

    async def release(self, symbol: str, interval: str, client_id: str):
        """
        Desregistra un cliente. Si era el último, detiene y elimina el broadcaster.
        """
        key = f"{symbol.upper()}:{interval}"
        async with self._lock:
            broadcaster = self._broadcasters.get(key)
            if broadcaster is None:
                return

            await broadcaster.unsubscribe(client_id)

            # 🚀 REGLA DE LINGER (Grace Period v5.7.155 Master Gold)
            # No eliminamos el broadcaster inmediatamente. Esperamos 60 segundos por si el usuario recarga la página.
            if broadcaster.subscriber_count() == 0 and not broadcaster.persistent:
                async def _delayed_cleanup():
                    await asyncio.sleep(60.0) # 60 segundos de "Gracia"
                    async with self._lock:
                        if key in self._broadcasters and self._broadcasters[key].subscriber_count() == 0:
                            await self._broadcasters[key].stop()
                            del self._broadcasters[key]
                            logger.info(f"[REGISTRY] 🗑️ Broadcaster eliminado tras Grace Period: {key}")
                
                asyncio.create_task(_delayed_cleanup())
            elif broadcaster.subscriber_count() == 0 and broadcaster.persistent:
                pass

    async def force_garbage_collection(self):
        """Purgado manual de RAM para cumplir con el Stress Test Pilar 4.2."""
        async with self._lock:
            # Eliminar broadcasters inactivos que ya pasaron su Grace Period
            for key in list(self._broadcasters.keys()):
                if self._broadcasters[key].subscriber_count() == 0 and not self._broadcasters[key].persistent:
                    await self._broadcasters[key].stop()
                    del self._broadcasters[key]
                    logger.info(f"[GARBAGE-COLLECTOR] 🧹 Liberada memoria de canal inactivo: {key}")

    def status(self) -> dict:
        """Retorna el estado del registry para el endpoint /health."""
        return {
            key: {"subscribers": b.subscriber_count()}
            for key, b in self._broadcasters.items()
        }


# Instancia global — importada por main.py
registry = BroadcasterRegistry()
