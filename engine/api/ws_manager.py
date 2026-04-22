"""
ws_manager.py — SymbolBroadcaster v6.0.1 (Refactor ISS-011)
=========================================================
Arquitectura: "Compute Once, Fan-Out N"

Un SymbolBroadcaster por símbolo activo:
  - Mantiene UNA conexión a Binance WS
  - Ejecuta el pipeline completo (SlingshotRouter) una sola vez
  - Distribuye el resultado a TODOS los clientes via asyncio.Queue

Módulos extraídos (v6.0.1 — Refactor ISS-011):
  registry.py        → BroadcasterRegistry
  signal_handler.py  → SignalHandler (filtrado, persistencia, Telegram)
  advisor_bridge.py  → AdvisorBridge (LLM Advisor, Ghost Data, caché semántica)
"""

from engine.api.registry import registry
from engine.core.logger import logger
import asyncio
try:
    import orjson as json
except ImportError:
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
from engine.router.processors import StreamProcessor
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
from engine.api.advisor import generate_tactical_advice, check_ollama_status
from engine.core.store import store
from engine.indicators.htf_analyzer import HTFAnalyzer
from engine.indicators.onchain import OnChainSentinel

# ✅ v6.0.1 — Módulos extraídos (Refactor ISS-011)
from engine.api.signal_handler import SignalHandler
from engine.api.advisor_bridge import AdvisorBridge

# 🏛️ (v6.0-Audit) La gestión de concurrencia IA ha migrado a advisor.py (Priority Queue)
# 🏛️ (v6.0-Strategy Delta) MASTER_WATCHLIST y PRIORITY_TIERS han migrado a config.py
# ──────────────────────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────────────────────
# Helpers compartidos
# ──────────────────────────────────────────────────────────────────────────────

async def fetch_binance_history(symbol: str, interval: str = "15m", limit: int = 300) -> list:
    """Descarga velas históricas desde Binance REST. Retorna lista de dicts estandarizados."""
    # v8.5.7: Migrado a fapi.binance.com para consistencia con On-Chain y mejores limites de tasa
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {"symbol": symbol.upper(), "interval": interval, "limit": limit}
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        response = await client.get(url, params=params)
        if response.status_code != 200:
            logger.debug(f"[HISTORY] Error {response.status_code} fetching {symbol} {interval}. Trying mirror...")
            # Fallback simple a espejo
            url = "https://fapi1.binance.com/fapi/v1/klines"
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
        self._cached_live_dates = None  # ✅ ISS-012: Inicializado para evitar AttributeError en cleanup

        # ✅ v6.0.1 — Módulos extraídos (Refactor ISS-011)
        self._signal_handler  = SignalHandler(self.symbol, self.interval, self)
        self._advisor_bridge  = AdvisorBridge(self.symbol, self.interval, self)

        # Alias de compatibilidad para el caché de advisor (leído por main.py)
        self._last_advisor = self._advisor_bridge._last_advisor_obj

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
        # [v8.2.0] Sincronizar todas las señales ACTIVAS, delegamos el margen de supervivencia al backend.
        for sig in list(last_signals)[-20:]:
            if sig.get("status") == "ACTIVE":
                await queue.put({"type": "signal_auditor_update", "data": sig})

        # ✅ SYNC INSTANTÁNEO: Radar Center (Global Context)
        if registry._last_radar_summary:
            await queue.put({"type": "radar_update", "data": registry._last_radar_summary})

        # ✅ HYDRATION: Noticias (v5.9.11 Master Fix)
        # Solo sincronizamos historial para el canal de 15m (Capitán) para evitar duplicados masivos 
        # al cambiar de temporalidad. También aumentamos a 15 items para visión total.
        if self.interval == "15m":
            try:
                latest_news = await store.get_news(limit=15)
                for news_item in reversed(list(latest_news)):
                    await queue.put({"type": "news_update", "data": news_item})
            except Exception as e:
                logger.error(f"[BROADCASTER] Hydration error: {e}")

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
        
        # [AUDITORIA v8.3.0] Validación de pertenencia de asset
        if msg_type in ["tactical_update", "signal_auditor_update", "execution_update"]:
            payload = clean.get("data", {})
            asset = payload.get("asset") if isinstance(payload, dict) else payload.get("symbol") if isinstance(payload, dict) else "?"
            if asset and asset != self.symbol and asset != "?":
                logger.error(f"🚨 [LEAK DETECTED] Broadcaster {self.symbol} emitio payload de {asset}! Bloqueando propogación.")
                return # Veto preventivo para evitar contaminar el frontend

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
        """[OPTIMIZACIÓN v8.5.1] Carga PROGRESIVA: 15m primero, Macro después."""
        logger.info(f"[BROADCASTER] {self._key} → Iniciando Bootstrap Progresivo...")

        # --- FASE 1: Prioridad Máxima (15m History para la UI) ---
        try:
            history = await fetch_binance_history(self.symbol, self.interval, limit=300)
            if history:
                self._history = sanitize_for_json(history)
                self._live_buffer = deque(self._history[-300:], maxlen=300)
                # Emitir historial inmediatamente para que el usuario vea el gráfico
                await self._broadcast({"type": "history", "data": self._history})
                logger.info(f"[BROADCASTER] {self._key} → 🟢 UI Hydrated (15m).")

                # --- SMC LIGHTNING-START (Fase Ultra Rápida) ---
                try:
                    df_fast = pd.DataFrame([i["data"] for i in self._history[-60:]]) # 60 velas para asegurar promedios
                    df_fast["timestamp"] = pd.to_datetime(df_fast["timestamp"], unit="s")
                    df_fast_ob = identify_order_blocks(df_fast)
                    fast_smc = extract_smc_coordinates(df_fast_ob)
                    await self._broadcast({"type": "smc_data", "data": fast_smc})
                    logger.info(f"[BROADCASTER] {self._key} → ⚡ SMC Lightning-Start completado.")
                except Exception as e:
                    logger.warning(f"[BROADCASTER] {self._key} → Lightning SMC fallido: {e}")
        except Exception as e:
            logger.error(f"[BROADCASTER] {self._key} → Error en carga crítica 15m: {e}")
            history = []

        # La función _load_background_data original estaba duplicada aquí. Se eliminó para mantener solo la versión completa inferior que incluye Liquidaciones, SMC y Drift Monitor.

        # --- FASE 2: Carga y Cálculos Pesados en Segundo Plano ---
        async def _load_background_data():
            try:
                # 1. Peticiones Macro
                tasks = [
                    fetch_binance_history(self.symbol, "1h", limit=250),
                    fetch_binance_history(self.symbol, "4h", limit=250),
                    self._advisor_bridge.refresh_ghost()
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                h1_raw = results[0] if not isinstance(results[0], Exception) else []
                h4_raw = results[1] if not isinstance(results[1], Exception) else []

                # 2. Cálculos de Indicadores (SMC, Liquidaciones, etc.)
                if history:
                    df_init = pd.DataFrame([i["data"] for i in history])
                    df_init["timestamp"] = pd.to_datetime(df_init["timestamp"], unit="s")
                    
                    # Precio de referencia para cálculos iniciales
                    ref_price = self.latest_price if self.latest_price > 0 else df_init["close"].iloc[-1]

                    # Liquidaciones y SMC (Pesados)
                    liq_clusters = estimate_liquidation_clusters(df_init, ref_price)
                    await self._broadcast({"type": "liquidation_update", "data": liq_clusters})

                    df_ob = identify_order_blocks(df_init)
                    smc_new = extract_smc_coordinates(df_ob)
                    self._persistent_smc = smc_new
                    await self._broadcast({"type": "smc_data", "data": self._persistent_smc})

                    # Drift Monitor
                    try:
                        from engine.inference.drift_monitor import drift_monitor
                        from engine.ml.feature_engineer import FeatureEngineer
                        fe = FeatureEngineer()
                        drift_monitor.set_reference(fe.generate_features(df_init.copy()))
                    except: pass

                    # On-Chain
                    try:
                        onchain_summary = await self._onchain_sentinel.refresh(
                            current_price=ref_price,
                            market_regime=df_init["market_regime"].iloc[-1] if "market_regime" in df_init.columns else "UNKNOWN"
                        )
                        await self._broadcast({"type": "onchain_update", "data": onchain_summary})
                    except: pass

                # 3. Macro Niveles y HTF Bias
                if h1_raw and h4_raw:
                    def _get_levels(raw, tf):
                        df = pd.DataFrame([i["data"] for i in raw])
                        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
                        df = identify_support_resistance(df, interval=tf)
                        return get_key_levels(df)

                    self._macro_levels = consolidate_mtf_levels(
                        _get_levels(h1_raw, "1h"), _get_levels(h4_raw, "4h"), timeframe_weight=3
                    )
                    await self._refresh_htf_bias()
                    
                    # Notificar actualización táctica final
                    if history:
                        await self._reprocess_initial_tactical(history)

            except Exception as bg_e:
                logger.error(f"[BROADCASTER] {self._key} → Error en cálculos de segundo plano: {bg_e}")

        # Disparamos todo el procesamiento pesado de forma asíncrona
        asyncio.create_task(_load_background_data())

        # 4. Inicialización mínima para el Stream Live (Sesiones)
        if history:
            try:
                self._session_manager.bootstrap([i["data"] for i in history])
                await self._broadcast(self._session_manager.get_current_state())
            except: pass

    async def _reprocess_initial_tactical(self, history):
        """Re-procesa el pipeline táctico una vez que los niveles macro están listos."""
        try:
            df = pd.DataFrame([i["data"] for i in history])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
            
            self._router.set_context(session_data=self._session_manager.get_current_state().get("data", {}))
            tactical = self._router.process_market_data(
                df, asset=self.symbol, interval=self.interval,
                macro_levels=self._macro_levels,
                htf_bias=self._htf_bias
            )
            
            # Hidratación con caché si existe
            cached = await self._store.get_advisor_advice(self.symbol)
            if cached:
                tactical["advisor_log"] = cached

            await self._broadcast({"type": "tactical_update", "data": tactical})
            logger.info(f"[BROADCASTER] {self._key} → 🔄 Pipeline táctico actualizado con niveles Macro.")
        except Exception as e:
            logger.error(f"[BROADCASTER] {self._key} → Error re-procesando táctico: {e}")

    # ── Stream en tiempo real (Fase 2 del stream) ────────────────────────────

    async def _stream_live(self):
        """Conexión al stream multiplexado de Binance (Capa de Red Pura)."""
        # 1. Source Check: Futures Mark Price (Optimizado v8.5.6)
        try:
            # Skip check para activos sin futuros
            if self.symbol in ["PAXGUSDT", "EURUSDT", "USDCUSDT"]:
                raise ValueError("Skip Futures Check: Spot Asset")

            futures_stream_url = f"wss://fstream.binance.com/ws/{self.symbol.lower()}@markPrice"
            async with ws_client.connect(futures_stream_url, open_timeout=3) as fws:
                await fws.recv() 
                logger.info(f"[SOURCE_CHECK] fapi.binance.com (Futures) OK.")
        except Exception as e:
            logger.debug(f"[SOURCE_CHECK] Futures check skipped for {self.symbol}: {e}")

        kline_stream = f"{self.symbol.lower()}@kline_{self.interval}"
        depth_stream = f"{self.symbol.lower()}@depth20@100ms"
        binance_url  = f"wss://stream.binance.com:9443/stream?streams={kline_stream}/{depth_stream}"

        # 🛡️ PROTECCIÓN DE HANDSHAKE (Thundering Herd Prevention)
        import random
        await asyncio.sleep(random.uniform(0.1, 2.0))
        
        logger.info(f"[BROADCASTER] {self._key} → Conectando a Binance WS: {binance_url}")

        async with ws_client.connect(
            binance_url, 
            ping_interval=20, 
            ping_timeout=20,
            open_timeout=30, 
            close_timeout=10
        ) as binance_ws:
            logger.info(f"[BROADCASTER] {self._key} → Stream EN VIVO 🟢")
            
            # EL BUCLE PRINCIPAL AHORA TIENE COMPLEJIDAD CICLOMÁTICA DE 3.
            while True:
                raw = await asyncio.wait_for(binance_ws.recv(), timeout=30.0)
                data = json.loads(raw)
                stream_type = data.get("stream", "")
                payload_data = data.get("data", {})

                # Dispatcher de Capa 1
                if stream_type == depth_stream:
                    self._process_depth_stream(payload_data)
                elif stream_type.startswith(self.symbol.lower()):
                    await self._process_kline_stream(payload_data, data)
                else:
                    logger.warning(f"⚠️ [SYSTEM] Cross-stream leak detected! {stream_type} discarded.")

    # ---------------------------------------------------------------------
    # DELEGADOS DE EJECUCIÓN (AISLAMIENTO DE COMPLEJIDAD)
    # ---------------------------------------------------------------------

    def _process_depth_stream(self, payload_data: dict):
        """Procesa exclusivamente el Neural Heatmap (Fast Path visual)."""
        price = self.latest_price or 1.0
        self._heatmap = analyze_neural_heatmap(
            bids=payload_data.get("bids", []),
            asks=payload_data.get("asks", []),
            current_price=price
        )
        self._liquidity = {
            "bids": [{"price": b["price"], "volume": b["volume"]} for b in self._heatmap.get("hot_bids", [])],
            "asks": [{"price": a["price"], "volume": a["volume"]} for a in self._heatmap.get("hot_asks", [])]
        }

    async def _process_kline_stream(self, payload_data: dict, raw_data: dict):
        """Enrutador de velas: Separa el Fast Path (Tick) del Slow Path (Close)."""
        kline = payload_data.get("k")
        if not kline:
            return

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

        # OMEGA CENTINEL
        from engine.execution.omega_listener import omega_centinel
        await omega_centinel.check_live_price(self.symbol, float(kline["c"]), self)

        # SESIONES
        self._session_manager.update(candle_payload["data"])
        await self._broadcast(self._session_manager.get_current_state())

        # ENRUTAMIENTO BIFURCADO
        await self._execute_fast_path(candle_payload, raw_data)
        
        if kline.get("x", False):
            await self._execute_slow_path(candle_payload)

    async def _execute_fast_path(self, candle_payload: dict, raw_data: dict):
        """Lógica de inter-vela (Tiered Priority)."""
        now = time.time()
        pulse_interval = settings.PRIORITY_TIERS.get(self.symbol, settings.DEFAULT_PULSE_INTERVAL)
        
        regime = self._last_tactical.get("data", {}).get("market_regime", "UNKNOWN") if self._last_tactical else "UNKNOWN"
        if regime in ["CHOPPY", "ACCUMULATION", "DISTRIBUTION"]:
            pulse_interval = max(pulse_interval, 3.0) 
        
        if now - self._last_pulse_ts < pulse_interval:
            return  # Rate Limiter Institucional Activo
            
        self._last_pulse_ts = now
        current_buffer = [i["data"] for i in self._live_buffer] + [candle_payload["data"]]
        df_live = pd.DataFrame(current_buffer)
        
        delta_fast = await StreamProcessor.process_fast_path(
            symbol=self.symbol, interval=self.interval,
            candle_payload=candle_payload, ws_data=raw_data,
            context={"df_live": df_live, "avg_volume": getattr(store, 'get_avg_volume', lambda x: 0)(self.symbol)}
        )

        from engine.api.registry import registry
        registry.record_latency(delta_fast.get("latency_ms", 0))

        if delta_fast.get("latency_dirty"):
            await self._broadcast({"type": "neural_log", "data": {"type": "SYSTEM", "message": f"⚠️ LATENCY_DIRTY: {delta_fast['latency_ms']}ms"}})
            
        if delta_fast.get("event") == "ABSORPTION_ALERT":
            logger.warning(f"[DELTA] 🚨 ABSORCIÓN detectada en {self.symbol}")
            await self._broadcast({"type": "absorption_alert", "data": {"rvol": delta_fast['rvol']}})
            asyncio.create_task(self._emit_advisor(self._last_tactical or {}, SessionManager.get_global_session_status(), is_absorption_alert=True))

        ml_data = delta_fast.get("ml_prediction", {})
        if ml_data:
            self._last_ml = ml_data
            prob_raw = ml_data.get("probability", 50)
            prob_bull = prob_raw if ml_data.get("direction") == "ALCISTA" else 100 - prob_raw
            self._ema_ml_prob = (prob_bull * self._ml_alpha) + (self._ema_ml_prob * (1 - self._ml_alpha))

        try:
            live_tactical = await asyncio.to_thread(
                self._router.process_market_data, df_live, asset=self.symbol, interval=self.interval,
                macro_levels=self._macro_levels, htf_bias=self._htf_bias, heatmap=self._heatmap, silent=True,
                event_time_ms=raw_data.get("data", {}).get("E")
            )
            self._last_tactical = {"data": live_tactical}
            self._live_rvol = float((live_tactical.get('diagnostic') or {}).get('rvol', 0))
            
            for sig in live_tactical.get("signals", []):
                await self._broadcast({"type": "signal_auditor_update", "data": sig})
                logger.info(f"🚀 [WS_PUSH] Señal APROBADA: {sig['asset']}")

            for sig in live_tactical.get("blocked_signals", []):
                await self._broadcast({"type": "signal_auditor_update", "data": sig})

            await self._broadcast({"type": "tactical_update", "data": live_tactical})
        except Exception as e:
            logger.error(f"[FAST-PATH] Pipeline tactical error: {e}")

        await self._broadcast({
            "type": "neural_pulse",
            "data": {"ml_projection": self._last_ml, "liquidity_heatmap": self._heatmap, "latency_ms": delta_fast.get("latency_ms", 0), "rvol_live": self._live_rvol}
        })

    async def _execute_slow_path(self, candle_payload: dict):
        """Lógica de cierre de vela (Strategy Delta Δ)."""
        self._processed_signals_this_candle.clear()
        self._live_buffer.append(candle_payload)
        self._candle_closes += 1
        
        delta_slow = await StreamProcessor.process_slow_path(
            symbol=self.symbol, candle_payload=candle_payload,
            live_buffer=list(self._live_buffer), persistent_smc=self._persistent_smc,
            context={"candle_closes": self._candle_closes, "ml_direction": self._ml_direction}
        )

        if delta_slow.get("smc_data"):
            self._persistent_smc = delta_slow["smc_data"]
            await self._broadcast({"type": "smc_data", "data": self._persistent_smc})

        if delta_slow.get("liquidation_clusters"):
            await self._broadcast({"type": "liquidation_update", "data": delta_slow["liquidation_clusters"]})

        try:
            df_slow = pd.DataFrame([i["data"] for i in self._live_buffer])
            df_slow["timestamp"] = pd.to_datetime(df_slow["timestamp"], unit="s")

            news_items   = await self._store.get_news()
            econ_events  = await self._store.get_economic_events(limit=5)
            
            self._router.set_context(
                ml_projection=self._last_ml, session_data=(self._last_session or {}).get("data", {}),
                news_items=news_items, economic_events=econ_events, liquidation_clusters=delta_slow.get("liquidation_clusters", [])
            )
            
            final_tactical = await asyncio.to_thread(
                self._router.process_market_data, df_slow, asset=self.symbol, interval=self.interval,
                macro_levels=self._macro_levels, htf_bias=self._htf_bias, silent=False
            )
            await self._broadcast({"type": "tactical_update", "data": final_tactical})
            await self._handle_signals(final_tactical, silent=False)

            current_candle_ts = str(candle_payload["data"]["timestamp"])
            if current_candle_ts != str(self._last_advisor_ts):
                self._last_advisor_ts = current_candle_ts
                asyncio.create_task(self._emit_advisor(final_tactical, SessionManager.get_global_session_status()))

        except Exception as e:
            logger.error(f"[SLOW-PATH] tactical error: {e}")

        if delta_slow.get("cleanup_event") == "CLEANUP_PERFORMED":
            self._history.clear()
            self._cached_live_dates = None
            logger.info(f"[DELTA] 🧹 Limpieza de memoria completada para {self.symbol}")


    async def _refresh_htf_bias(self):
        """Re-evalúa el sesgo institucional (4H + 1H) para el enrutamiento top-down."""
        try:
            h1_raw = await fetch_binance_history(self.symbol, "1h", limit=250)
            h4_raw = await fetch_binance_history(self.symbol, "4h", limit=250)
            
            if not h1_raw or not h4_raw:
                raise ValueError("API devolvió datos vacíos para HTF Bias")
                
            df_h1 = pd.DataFrame([i["data"] for i in h1_raw])
            df_h4 = pd.DataFrame([i["data"] for i in h4_raw])
            
            df_h1["timestamp"] = pd.to_datetime(df_h1["timestamp"], unit="s")
            df_h4["timestamp"] = pd.to_datetime(df_h4["timestamp"], unit="s")
            
            self._htf_bias = self._htf_analyzer.analyze_bias(df_h4, df_h1)
            self._last_htf_ts = time.time()
            
            logger.debug(f"[BROADCASTER] {self._key} → 🧭 HTF Bias Refrescado: {self._htf_bias.direction}")
        except Exception as e:
            logger.error(f"[BROADCASTER] {self._key} → Error refrescando HTF Bias: {e}")
            # Fallback seguro para evitar UI congelada en "Analizando..."
            from engine.core.confluence import HTFBias
            self._htf_bias = HTFBias(
                direction="NEUTRAL",
                strength=0.0,
                reason="Calibrando temporalidad superior...",
                h4_regime="STANDBY",
                h1_regime="STANDBY"
            )

    # ── Handlers auxiliares ───────────────────────────────────────────────────

    async def check_ollama(self) -> bool:
        """Prueba rápida asincrónica para ver si Ollama responde en localhost:11434."""
        import httpx
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                r = await client.get("http://localhost:11434/api/tags")
                return r.status_code == 200
        except:
            return False

    async def _handle_signals(self, tactical: dict, silent: bool = False):
        """Delega al SignalHandler extraído (v6.0.1 — Refactor ISS-011)."""
        await self._signal_handler.handle(tactical, silent=silent)

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
                    "asset": self._symbol,  # [FORCED v8.3.0] Prohibir asset leakage
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



    async def _persist_signal(self, sig: dict, tactical: dict, status: str = "ACTIVE", rejection_reason: str = None, silent: bool = False):
        """Delega al SignalHandler extraído (v6.0.1 — Refactor ISS-011)."""
        await self._signal_handler.persist(sig, tactical, status=status, rejection_reason=rejection_reason, silent=silent)

    def _get_tactical_hash(self, tactical: dict) -> str:
        """Delega al AdvisorBridge extraído (v6.0.1 — Refactor ISS-011)."""
        return self._advisor_bridge.get_tactical_hash(tactical)

    async def _emit_advisor(self, tactical: dict, session_state: dict, is_absorption_alert: bool = False):
        """Delega al AdvisorBridge extraído (v6.0.1 — Refactor ISS-011)."""
        await self._advisor_bridge.emit(tactical, session_state, is_absorption_alert=is_absorption_alert)

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


# ──────────────────────────────────────────────────────────────────────────────
# (v6.0) BroadcasterRegistry ha migrado a engine/api/registry.py (Strategy Delta)
# ──────────────────────────────────────────────────────────────────────────────
