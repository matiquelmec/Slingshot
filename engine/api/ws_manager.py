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

import asyncio
import json
import time
import traceback
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
    identify_support_resistance, get_key_levels, consolidate_mtf_levels
)
from engine.indicators.liquidations import estimate_liquidation_clusters
from engine.indicators.liquidity import detect_liquidity_clusters
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


# ──────────────────────────────────────────────────────────────────────────────
# Helpers compartidos
# ──────────────────────────────────────────────────────────────────────────────

async def fetch_binance_history(symbol: str, interval: str = "15m", limit: int = 1000) -> list:
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
        self._router         = SlingshotRouter()
        self._session_manager = SessionManager(symbol=self.symbol)
        self._history: list  = []
        self._macro_levels   = None
        self._live_buffer: deque = deque(maxlen=1000)
        self._last_ml        = {"direction": "CALIBRANDO", "probability": 50, "status": "warmup"}
        self._ema_ml_prob    = 50.0
        self._ml_alpha       = 0.2
        self._ml_direction   = "ANALIZANDO"
        self._candle_closes  = 0
        self._last_pulse_ts  = 0.0
        self._liquidity      = {"bids": [], "asks": []}
        
        # ML Tracking Buffer: guarda [timestamp, precio, dirección_predicha] para verificar N velas después
        self._prediction_history = deque(maxlen=20) 

        # HTF Top-Down Analysis (v4.0)
        self._htf_analyzer = HTFAnalyzer()
        self._htf_bias     = None
        self._last_htf_ts  = 0.0        
        # Caché del último estado para nuevos suscriptores
        self._last_ghost     = None
        self._last_smc       = None
        self._last_tactical  = None
        self._last_session   = None
        self._last_advisor   = None
        self._last_liquidations = None

        print(f"[BROADCASTER] ✅ Creado: {self._key}")

    # ── Suscripción ──────────────────────────────────────────────────────────

    async def subscribe(self, client_id: str) -> asyncio.Queue:
        """Registra un nuevo cliente. Retorna su Queue personal."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        async with self._lock:
            self._subscribers[client_id] = queue
            count = len(self._subscribers)
        print(f"[BROADCASTER] {self._key} → +cliente {client_id[:6]} (total: {count})")

        # Enviar historial actual y estado cacheado al nuevo cliente
        if self._history:
            await queue.put({"type": "history", "data": self._history})
        if self._last_ghost:    await queue.put(self._last_ghost)
        if self._last_smc:      await queue.put(self._last_smc)
        if self._last_tactical: await queue.put(self._last_tactical)
        if self._last_session:  await queue.put(self._last_session)
        if self._last_advisor:  await queue.put(self._last_advisor)
        if self._last_liquidations: await queue.put(self._last_liquidations)

        return queue

    async def unsubscribe(self, client_id: str):
        """Desregistra un cliente."""
        async with self._lock:
            self._subscribers.pop(client_id, None)
            count = len(self._subscribers)
        print(f"[BROADCASTER] {self._key} → -cliente {client_id[:6]} (total: {count})")

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
            await store.update_market_state(self.symbol, {"macro_bias": clean["data"].get("macro_bias")})
        elif msg_type == "smc_data":       
            self._last_smc = clean
        elif msg_type == "tactical_update":
            self._last_tactical = clean
            await store.update_market_state(self.symbol, {
                "regime": clean["data"].get("market_regime"),
                "strategy": clean["data"].get("active_strategy"),
                "price": float(clean["data"].get("current_price", 0))
            })
        elif msg_type == "session_update": 
            self._last_session  = clean
            await store.update_market_state(self.symbol, {"session": clean["data"].get("current_session")})
        elif msg_type == "advisor_update": 
            self._last_advisor  = clean
        elif msg_type == "liquidation_update":
            self._last_liquidations = clean
            await store.update_liquidation_clusters(self.symbol, clean["data"])
        elif msg_type == "candle":
            await store.save_candle(self.symbol, self.interval, clean)
            await store.update_market_state(self.symbol, {"price": float(clean["data"].get("close", 0))})
        
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
                    print(f"[BROADCASTER] {self._key} → cliente {cid[:6]} eliminado (queue llena)")

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
        print(f"[BROADCASTER] 🛑 Detenido: {self._key}")

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
                print(f"[BROADCASTER] ⚠️ Error en {self._key}: {e}. Reintentando en {retry_delay}s...")
                traceback.print_exc()
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60.0)  # exponential backoff, máx 60s

    # ── Bootstrap (Fase 1 del stream) ────────────────────────────────────────

    async def _bootstrap(self):
        """Descarga historial inicial y envía los primeros payloads a todos los clientes."""
        print(f"[BROADCASTER] {self._key} → Descargando historial desde Binance REST...")

        # 1. Historial de velas
        try:
            history = await fetch_binance_history(self.symbol, self.interval, limit=1000)
            self._history = sanitize_for_json(history)
            self._live_buffer = deque(self._history[-1000:], maxlen=1000)
            await self._broadcast({"type": "history", "data": history})
            print(f"[BROADCASTER] {self._key} → {len(history)} velas enviadas.")
        except Exception as e:
            print(f"[BROADCASTER] {self._key} → Binance REST falló: {e}")
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
                print(f"[BROADCASTER] {self._key} → Niveles macro consolidados.")
            except Exception as e:
                print(f"[BROADCASTER] {self._key} → MTF fallido: {e}")

        # 3. Ghost Data (Fear & Greed, BTCD, Funding específico)
        try:
            asyncio.create_task(self._refresh_ghost())
        except Exception as e:
            print(f"[BROADCASTER] {self._key} → Ghost Data inicial error: {e}")

        # 3.5 HTF Bias Analysis (4H + 1H)
        try:
            await self._refresh_htf_bias()
        except Exception as e:
            print(f"[BROADCASTER] {self._key} → HTF Bias inicial error: {e}")

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
                print(f"[BROADCASTER] {self._key} → Sesión bootstrap error: {e}")

            # Liquidaciones iniciales (Trapped Money)
            try:
                liq_clusters = estimate_liquidation_clusters(df_init, self.latest_price)
                await self._broadcast({"type": "liquidation_update", "data": liq_clusters})
            except Exception as e:
                print(f"[BROADCASTER] {self._key} → Initial Liquidation error: {e}")

            # Drift Monitor — referencia inicial
            try:
                fe = FeatureEngineer()
                df_features = fe.generate_features(df_init.copy())
                drift_monitor.set_reference(df_features)
            except Exception as e:
                print(f"[BROADCASTER] {self._key} → Drift reference error: {e}")

            # SMC inicial
            try:
                df_ob = identify_order_blocks(df_init)
                smc   = extract_smc_coordinates(df_ob)
                await self._broadcast({"type": "smc_data", "data": smc})
            except Exception as e:
                print(f"[BROADCASTER] {self._key} → SMC inicial error: {e}")

            # Pipeline táctico inicial
            try:
                self._router.set_context(session_data=self._session_manager.get_current_state().get("data", {}))
                tactical = self._router.process_market_data(
                    df_init.copy(), asset=self.symbol, interval=self.interval,
                    macro_levels=self._macro_levels,
                    htf_bias=self._htf_bias
                )
                await self._broadcast({"type": "tactical_update", "data": tactical})

                # LLM Advisor inicial (no bloqueante)
                asyncio.create_task(self._emit_advisor(tactical, self._session_manager.get_current_state()))
            except Exception as e:
                print(f"[BROADCASTER] {self._key} → Pipeline inicial error: {e}")

    # ── Stream en tiempo real (Fase 2 del stream) ────────────────────────────

    async def _stream_live(self):
        """Conexión al stream multiplexado de Binance (klines + depth)."""
        kline_stream = f"{self.symbol.lower()}@kline_{self.interval}"
        depth_stream = f"{self.symbol.lower()}@depth20@100ms"
        binance_url  = f"wss://stream.binance.com:9443/stream?streams={kline_stream}/{depth_stream}"

        print(f"[BROADCASTER] {self._key} → Conectando a Binance WS: {binance_url}")

        async with ws_client.connect(binance_url) as binance_ws:
            print(f"[BROADCASTER] {self._key} → Stream EN VIVO 🟢")
            while True:
                raw = await asyncio.wait_for(binance_ws.recv(), timeout=30.0)
                data = json.loads(raw)
                stream_type = data.get("stream", "")
                payload_data = data.get("data", {})

                # ── Order Book Depth ──────────────────────────────────────────
                if stream_type == depth_stream:
                    self._liquidity = detect_liquidity_clusters(
                        bids=payload_data.get("bids", []),
                        asks=payload_data.get("asks", []),
                        top_n=3
                    )
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

                # ── FAST PATH (Dinámico: 1s a 5s) ─────────────────────────────
                now = time.time()
                
                # Definir intervalo de pulso dinámico
                pulse_interval = 1.0  # Default (TRENDING o alta actividad)
                regime = self._last_tactical.get("data", {}).get("market_regime", "UNKNOWN") if self._last_tactical else "UNKNOWN"
                
                if regime in ["CHOPPY", "ACCUMULATION", "DISTRIBUTION"]:
                    pulse_interval = 3.0  # Reducir frecuencia en mercados laterales
                
                if now - self._last_pulse_ts >= pulse_interval:
                    self._last_pulse_ts = now

                    # Sincronización con Ghost Data Centralizado
                    ghost = get_ghost_state()
                    if not ghost.is_stale and (not self._last_ghost or ghost.last_updated > self._last_ghost.get("data", {}).get("last_updated", 0)):
                        await self._refresh_ghost(ghost)

                    # Refresco Periódico de HTF Bias (cada 30 min)
                    if now - self._last_htf_ts > 1800: # 30 min
                         asyncio.create_task(self._refresh_htf_bias())

                    # ML Inference (XGBoost, <50ms)
                    current_buffer = [i["data"] for i in self._live_buffer] + [candle_payload["data"]]
                    if len(current_buffer) > 50:
                        df_tick = pd.DataFrame(current_buffer)
                        df_tick["timestamp"] = pd.to_datetime(df_tick["timestamp"], unit="s")

                        raw_pred = ml_engine.predict_live(df_tick)
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

                        # Pipeline táctico en Fast Path
                        try:
                            live_tactical = self._router.process_market_data(
                                df_tick, asset=self.symbol, interval=self.interval,
                                macro_levels=self._macro_levels,
                                htf_bias=self._htf_bias
                            )
                            await self._broadcast({"type": "tactical_update", "data": live_tactical})
                            
                            # 🚀 HEARTBEAT DE ESCANEO: Para que el usuario vea que el motor está vivo
                            if live_tactical.get("market_regime") != "UNKNOWN":
                                status_msg = f"[SCAN] Sesgo: {self._htf_bias.direction if self._htf_bias else 'NEUTRAL'} | Régimen: {live_tactical.get('market_regime')} | Filtros OK"
                                await self._broadcast({"type": "neural_log", "data": {
                                    "type": "SYSTEM",
                                    "message": status_msg
                                }})

                            # 🚀 PERSISTENCIA EN TIEMPO REAL (Fast Path)
                            if live_tactical.get("signals"):
                                await self._handle_signals(live_tactical)
                        except Exception as e:
                            print(f"[BROADCASTER] {self._key} → Fast Path pipeline error: {e}")
                            traceback.print_exc()

                    # Neural Pulse
                    await self._broadcast({
                        "type": "neural_pulse",
                        "data": {
                            "ml_projection": self._last_ml,
                            "liquidity_heatmap": self._liquidity,
                            "log": {
                                "type": "SENSOR",
                                "message": f"[Fast Path] Precio: ${float(kline['c']):.2f}"
                            }
                        }
                    })

                # ── SLOW PATH: cierre de vela ─────────────────────────────────
                if kline.get("x", False):
                    self._live_buffer.append(candle_payload)
                    self._candle_closes += 1

                    df_live = pd.DataFrame([i["data"] for i in self._live_buffer])
                    df_live["timestamp"] = pd.to_datetime(df_live["timestamp"], unit="s")

                    # Drift Monitor (cada 100 velas cerradas ≈ 25h en 15m)
                    if self._candle_closes % 100 == 0:
                        asyncio.create_task(self._check_drift(df_live.copy()))

                    # SMC actualizado
                    try:
                        df_ob = identify_order_blocks(df_live)
                        smc   = extract_smc_coordinates(df_ob)
                        await self._broadcast({"type": "smc_data", "data": smc})
                    except Exception as e:
                        print(f"[BROADCASTER] {self._key} → SMC Slow Path error: {e}")

                    # Liquidaciones Sintéticas (Trapped Money)
                    try:
                        liq_clusters = estimate_liquidation_clusters(df_live, self.latest_price)
                        await self._broadcast({"type": "liquidation_update", "data": liq_clusters})
                    except Exception as e:
                        print(f"[BROADCASTER] {self._key} → Liquidation Estimator error: {e}")

                    # Pipeline táctico final (vela cerrada = máxima precisión)
                    try:
                        news_items = await store.get_news()
                        self._router.set_context(
                            ml_projection=self._last_ml,
                            session_data=session_state.get("data", {}),
                            news_items=news_items
                        )
                        final_tactical = self._router.process_market_data(
                            df_live, asset=self.symbol, interval=self.interval,
                            macro_levels=self._macro_levels,
                            htf_bias=self._htf_bias
                        )
                        await self._broadcast({"type": "tactical_update", "data": final_tactical})

                        # Filtro macro + Telegram + Supabase
                        await self._handle_signals(final_tactical)

                    except Exception as e:
                        print(f"[BROADCASTER] {self._key} → Slow Path pipeline error: {e}")

                    # Sesión con cierre confirmado
                    try:
                        session_state = self._session_manager.update(candle_payload["data"], is_closed=True)
                        await self._broadcast(session_state)
                    except Exception as e:
                        print(f"[BROADCASTER] {self._key} → Session Slow Path error: {e}")

                    # LLM Advisor (no bloqueante)
                    asyncio.create_task(self._emit_advisor(final_tactical, session_state))

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
            
            print(f"[BROADCASTER] {self._key} → 🧭 HTF Bias Refrescado: {self._htf_bias.direction} ({self._htf_bias.reason})")
        except Exception as e:
            print(f"[BROADCASTER] {self._key} → Error refrescando HTF Bias: {e}")

    # ── Handlers auxiliares ───────────────────────────────────────────────────

    async def _handle_signals(self, tactical: dict):
        """Filtra por macro, notifica por Telegram y persiste en MemoryStore local (v3.0).
        En Audit Mode: también persiste las señales RECHAZADAS por el Portero Institucional o HTF.
        """
        raw_signals = tactical.get("signals", [])
        # ✅ CORRECCIÓN: Recoger también las señales bloqueadas por el router (Portero R:R o HTF)
        router_blocked = tactical.get("blocked_signals", [])

        # Si no hay nada en absoluto, salir
        if not raw_signals and not router_blocked:
            return

        ghost = get_ghost_state()
        approved, macro_blocked = filter_signals_by_macro(raw_signals, ghost)
        
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
                print(f"[BROADCASTER] {self._key} → 🔕 Telegram bloqueado: {reason}")
                sig["blocked_reason"] = reason
                macro_blocked.append(sig)
        
        # ──────── PERSISTIR ACTIVAS ────────
        for sig in final_approved:
            asyncio.create_task(self._persist_signal(sig, tactical, status="ACTIVE"))

        # ──────── PROCESAR BLOQUEADAS POR MACRO/FILTRO (Auditoría) ────────
        for sig in macro_blocked:
            motivo = sig.get("blocked_reason", "Bloqueada por filtro macro (miedo/funding/dominancia)")
            status = "BLOCKED_BY_MACRO" if "macro" in motivo.lower() or "miedo" in motivo.lower() else "BLOCKED_BY_FILTER"
            asyncio.create_task(self._persist_signal(sig, tactical, status=status, rejection_reason=motivo))

        # ──────── PROCESAR BLOQUEADAS POR EL ROUTER (Audit Mode: R:R o HTF) ────────
        for sig in router_blocked:
            motivo = sig.get("blocked_reason", "Rechazada por filtro táctico")
            status = sig.get("status", "BLOCKED_BY_FILTER")
            asyncio.create_task(self._persist_signal(sig, tactical, status=status, rejection_reason=motivo))



    async def _persist_signal(self, sig: dict, tactical: dict, status: str = "ACTIVE", rejection_reason: str = None):
        """Inserta la señal en public.signal_events y en el MemoryStore local."""
        ghost = get_ghost_state()
        
        # Datos para tiempo real
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
            "timestamp":        datetime.now(timezone.utc).isoformat(),
            "confluence":       sig.get("confluence")
        }
        
        # Persistencia en Memoria Local
        asyncio.create_task(store.save_signal(realtime_data))
        
        # Emitir evento visual de auditoría al UI para que el Terminal HFT pestañee.
        await self._broadcast({"type": "signal_auditor_update", "data": realtime_data})
        
        # En v3.0, solo guardamos en memoria. Print de confirmación local.
        icon = "✅" if status == "ACTIVE" else "🚫"
        print(f"[LOCAL STORE] {icon} Señal ({status}) persistida: {realtime_data['signal_type']} {self.symbol} @ ${realtime_data['entry_price']:.2f}")

    async def _emit_advisor(self, tactical: dict, session_state: dict):
        """Llama al LLM Advisor y broadcast el resultado."""
        print(f"[BROADCASTER] 🧠 Iniciando análisis LLM para {self.symbol}...")
        try:
            # Enviar estado de 'Cargando' explícito si es necesario (opcional)
            # await self._broadcast({"type": "advisor_update", "data": "ANALIZANDO... ⚡"})

            # Obtener datos adicionales del store para el LLM
            news_items = await store.get_news(limit=5)
            liqs = await store.get_liquidation_clusters(self.symbol)
            econ_events = await store.get_economic_events(limit=5)

            # Timeout de 60 segundos para no colgar el worker
            advice = await asyncio.wait_for(
                generate_tactical_advice(self.symbol, 
                    tactical_data=tactical,
                    current_session=session_state.get("data", {}).get("current_session", "UNKNOWN"),
                    ml_projection=self._last_ml,
                    news=news_items,
                    liquidations=liqs,
                    economic_events=econ_events
                ),
                timeout=60.0
            ) 
            print(f"[BROADCASTER] ✅ Análisis LLM completado para {self.symbol}")
            await self._broadcast({"type": "advisor_update", "data": advice})
        except asyncio.TimeoutError:
            print(f"[BROADCASTER] ⚠️ Timeout en LLM Advisor ({self.symbol})")
            await self._broadcast({"type": "advisor_update", "data": "ADVISOR LOG: LLM_TIMEOUT. El motor de inferencia está saturado. Reintentando en la próxima vela."})
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[BROADCASTER] ❌ {self._key} → Advisor error: {e}")
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
            
            # 4. Broadcast
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
            }})
        except Exception as e:
            print(f"[BROADCASTER] {self._key} → Ghost specific refresh error: {e}")

    async def _check_drift(self, df: pd.DataFrame):
        """Ejecuta el drift monitor y broadcast alerta si hay drift."""
        try:
            fe = FeatureEngineer()
            df_features = fe.generate_features(df)
            report = drift_monitor.check(df_features)
            if report and report.alert_triggered:
                await self._broadcast({"type": "drift_alert", "data": report.to_dict()})
        except Exception as e:
            print(f"[BROADCASTER] {self._key} → Drift check error: {e}")


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

    async def start_global_pulse(self):
        """Inicia el latido global que sincroniza el estado de todos los radares."""
        if self._pulse_task: return
        self._pulse_task = asyncio.create_task(self._pulse_loop())
        print("[REGISTRY] 💓 Global Radar Pulse iniciado")

    async def _pulse_loop(self):
        """Loop que emite el estado resumido de todo el mercado cada 15 segundos."""
        while True:
            try:
                await asyncio.sleep(15)
                # 1. Obtener estados de todos los activos desde el store
                states = await store.get_market_states()
                if not states: continue

                # 2. Simplificar para el Radar (ahorro de ancho de banda)
                summary = []
                for s in states:
                    summary.append({
                        "asset":    s.get("asset"),
                        "price":    s.get("current_price"),
                        "regime":   s.get("regime", "UNKNOWN"),
                        "strategy": s.get("strategy", "STANDBY"),
                        "bias":     s.get("htf_bias", {}).get("bias", "NEUTRAL") if isinstance(s.get("htf_bias"), dict) else "NEUTRAL",
                        "trend":    s.get("sma_slow_slope", 0)
                    })

                # 3. Fan-out: Enviar a TODOS los broadcasters activos
                async with self._lock:
                    for b in self._broadcasters.values():
                        await b._broadcast({"type": "radar_update", "data": summary})
            except Exception as e:
                print(f"[REGISTRY] Pulse error: {e}")
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
                broadcaster = SymbolBroadcaster(symbol, interval, persistent=persistent)
                self._broadcasters[key] = broadcaster
                await broadcaster.start()
                print(f"[REGISTRY] ✅ Nuevo broadcaster: {key}")
            else:
                # Si ya existía pero no era persistente y ahora se pide persistencia (ej: por orquestador)
                if persistent and not self._broadcasters[key].persistent:
                    self._broadcasters[key].persistent = True
                    print(f"[REGISTRY] 💎 Broadcaster {key} elevado a PERSISTENTE")
                    
                print(f"[REGISTRY] ♻️  Reutilizando broadcaster: {key} ({self._broadcasters[key].subscriber_count()} clientes activos)")

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

            # 🚀 REGLA DE PERSISTENCIA: Los del Radar (persistent=True) NUNCA se eliminan.
            # Los que pide el usuario por el Dashboard (persistent=False) sí.
            if broadcaster.subscriber_count() == 0 and not broadcaster.persistent:
                await broadcaster.stop()
                del self._broadcasters[key]
                print(f"[REGISTRY] 🗑️  Broadcaster eliminado (sin clientes): {key}")
            elif broadcaster.subscriber_count() == 0 and broadcaster.persistent:
                # print(f"[REGISTRY] 🛡️  Broadcaster {key} mantenido en segundo plano (PERSISTENTE)")
                pass

    def status(self) -> dict:
        """Retorna el estado del registry para el endpoint /health."""
        return {
            key: {"subscribers": b.subscriber_count()}
            for key, b in self._broadcasters.items()
        }


# Instancia global — importada por main.py
registry = BroadcasterRegistry()
