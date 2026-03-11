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
import sys
import argparse
from collections import deque
from datetime import datetime, timezone
from typing import Dict, Optional
import uuid
import redis.asyncio as redis

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
from engine.indicators.liquidity import detect_liquidity_clusters
from engine.indicators.ghost_data import refresh_ghost_data, get_ghost_state, filter_signals_by_macro, is_cache_fresh
from engine.ml.features import FeatureEngineer
from engine.ml.inference import ml_engine
from engine.ml.drift_monitor import drift_monitor
from engine.notifications.telegram import send_signal_async
from engine.notifications.filter import signal_filter
from engine.api.advisor import generate_tactical_advice
from engine.api.supabase_client import supabase_service  # cliente Supabase service_role


# ──────────────────────────────────────────────────────────────────────────────
# Helpers compartidos
# ──────────────────────────────────────────────────────────────────────────────

async def fetch_binance_history(symbol: str, interval: str = "15m", limit: int = 500) -> list:
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

class SymbolWorker:
    """
    Worker autónomo por símbolo.
    Mantiene UNA conexión Binance WS, ejecuta el pipeline,
    y PUBLICA los resultados a Redis.
    """

    def __init__(self, symbol: str, interval: str, redis_pool: redis.Redis):
        self.symbol     = symbol.upper()
        self.interval   = interval
        self._key       = f"{self.symbol}:{self.interval}"
        self._redis     = redis_pool
        self._channel   = f"slingshot:stream:{self.symbol}:{self.interval}"
        self._state_key = f"slingshot:state:{self.symbol}:{self.interval}"

        self._task: Optional[asyncio.Task] = None

        # Estado interno del broadcaster (compartido entre todas las velas)
        self._router         = SlingshotRouter()
        self._session_manager = SessionManager(symbol=self.symbol)
        self._history: list  = []
        self._macro_levels   = None
        self._live_buffer: deque = deque(maxlen=500)
        self._last_ml        = {"direction": "CALIBRANDO", "probability": 50, "status": "warmup"}
        self._ema_ml_prob    = 50.0
        self._ml_alpha       = 0.2
        self._ml_direction   = "ANALIZANDO"
        self._candle_closes  = 0
        self._last_pulse_ts  = 0.0
        self._liquidity      = {"bids": [], "asks": []}
        
        # Caché del último estado para nuevos suscriptores
        self._last_ghost     = None
        self._last_smc       = None
        self._last_tactical  = None
        self._last_session   = None
        self._last_advisor   = None
        
        # Anti-Spam Firewall
        self._last_signals_sent = {} # (tipo) -> {"price": float, "ts": float}
        self._signal_cooldown = 300  # 5 minutos entre señales del mismo tipo

        print(f"[WORKER] ✅ Creado y enlazado a Redis: {self._key}")

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

    # ── Broadcast interno ────────────────────────────────────────────────────

    async def _broadcast(self, message: dict):
        """Envía un mensaje a Redis pub/sub y cachea el estado."""
        clean = sanitize_for_json(message)
        
        msg_type = clean.get("type", "")
        if msg_type == "ghost_update":     self._last_ghost    = clean
        elif msg_type == "smc_data":       self._last_smc      = clean
        elif msg_type == "tactical_update":self._last_tactical = clean
        elif msg_type == "session_update": self._last_session  = clean
        elif msg_type == "advisor_update": self._last_advisor  = clean
        
        # Publish to Redis channel
        await self._redis.publish(self._channel, json.dumps(clean))

        # Update latest state cache in Redis (useful for immediate bootstrap of new UI clients)
        if msg_type != "neural_pulse":
            try:
                state = {
                    "ghost_update": self._last_ghost,
                    "smc_data": self._last_smc,
                    "tactical_update": self._last_tactical,
                    "session_update": self._last_session,
                    "advisor_update": self._last_advisor
                }
                # Do NOT push the full history list into Redis on every tick to save IO and bandwidth
                if msg_type == "history":
                    state["history"] = self._history
                elif self._history:
                     state["history"] = [self._history[-1]] # Solo enviamos la vela live mas reciente para bootstrap

                await self._redis.set(self._state_key, json.dumps(state))
            except Exception as e:
                print(f"[REDIS] Error guardando cache: {e}")

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
            history = await fetch_binance_history(self.symbol, self.interval, limit=500)
            self._history = sanitize_for_json(history)
            self._live_buffer = deque(self._history[-500:], maxlen=500)
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

        # 3. Ghost Data (Fear & Greed, BTCD, Funding)
        try:
            ghost = await refresh_ghost_data(self.symbol)
            await self._broadcast({"type": "ghost_update", "data": {
                "fear_greed_value": ghost.fear_greed_value,
                "fear_greed_label": ghost.fear_greed_label,
                "btc_dominance":    ghost.btc_dominance,
                "funding_rate":     ghost.funding_rate,
                "macro_bias":       ghost.macro_bias,
                "block_longs":      ghost.block_longs,
                "block_shorts":     ghost.block_shorts,
                "reason":           ghost.reason,
                "last_updated":     ghost.last_updated,
            }})
        except Exception as e:
            print(f"[BROADCASTER] {self._key} → Ghost Data no disponible: {e}")

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

            # Drift Monitor — referencia inicial
            try:
                fe = FeatureEngineer()
                df_features = fe.generate_features(df_init.copy())
                drift_monitor.set_reference(df_features)
            except Exception as e:
                print(f"[BROADCASTER] {self._key} → Drift reference error: {e}")

            # SMC inicial
            try:
                # 💎 Sensibilidad Adaptativa para PAXG/Metales
                is_metal = self.symbol.upper() in ["PAXGUSDT", "XAGUSDT", "XAUUSDT", "GOLD", "SILVER"]
                smc_threshold = 1.6 if is_metal else 2.0
                
                df_ob = identify_order_blocks(df_init, threshold=smc_threshold)
                smc   = extract_smc_coordinates(df_ob)
                await self._broadcast({"type": "smc_data", "data": smc})
            except Exception as e:
                print(f"[BROADCASTER] {self._key} → SMC inicial error: {e}")

            # Pipeline táctico inicial
            try:
                self._router.set_context(session_data=self._session_manager.get_current_state().get("data", {}))
                tactical = self._router.process_market_data(
                    df_init.copy(), asset=self.symbol, interval=self.interval,
                    macro_levels=self._macro_levels
                )
                
                # 🔄 Sincronización con DB: Buscar señales actualmente activas en Supabase
                try:
                    from engine.api.supabase_client import supabase_service
                    if supabase_service:
                        active_db = supabase_service.table("signal_events").select("*")\
                            .eq("asset", self.symbol)\
                            .eq("status", "ACTIVE")\
                            .execute()
                        
                        if active_db.data:
                            # Fusionar preservando las más recientes encontradas por el router
                            # Nota: Estandarizamos campos de DB -> Motor/UI
                            db_sigs = active_db.data
                            existing_ids = {str(s.get('id')) for s in tactical.get('signals', [])}

                            for s in db_sigs:
                                # Mapeo de nombres Supabase -> Motor
                                if "signal_type" in s and "type" not in s: s["type"] = s["signal_type"]
                                if "entry_price" in s and "price" not in s: s["price"] = s["entry_price"]
                                if "take_profit" in s and "take_profit_3r" not in s: s["take_profit_3r"] = s["take_profit"]
                                if "created_at" in s and "timestamp" not in s: s["timestamp"] = s["created_at"]
                                
                                if str(s.get('id')) not in existing_ids:
                                    tactical['signals'].append(s)
                except Exception as e_db:
                    print(f"[BROADCASTER] ⚠️ Error sincronizando señales activas de DB: {e_db}")

                await self._broadcast({"type": "tactical_update", "data": tactical})

                # 🚀 Sincronizar señales encontradas con la DB
                await self._handle_signals(tactical)

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

                # ── FAST PATH (max 1 vez/segundo) ─────────────────────────────
                now = time.time()
                if now - self._last_pulse_ts >= 1.0:
                    self._last_pulse_ts = now

                    # Ghost Data auto-refresh si el caché está vencido
                    if not is_cache_fresh(self.symbol):
                        asyncio.create_task(self._refresh_ghost())

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
                                macro_levels=self._macro_levels
                            )
                            await self._broadcast({"type": "tactical_update", "data": live_tactical})
                            
                            # 🚀 PERSISTENCIA EN TIEMPO REAL (Fast Path)
                            # Si el router genera una nueva señal viva en este tick, la guardamos.
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
                        # 💎 Sensibilidad Adaptativa para PAXG/Metales
                        is_metal = self.symbol.upper() in ["PAXGUSDT", "XAGUSDT", "XAUUSDT", "GOLD", "SILVER"]
                        smc_threshold = 1.6 if is_metal else 2.0
                        
                        df_ob = identify_order_blocks(df_live, threshold=smc_threshold)
                        smc   = extract_smc_coordinates(df_ob)
                        await self._broadcast({"type": "smc_data", "data": smc})
                    except Exception as e:
                        print(f"[BROADCASTER] {self._key} → SMC Slow Path error: {e}")

                    # Pipeline táctico final (vela cerrada = máxima precisión)
                    try:
                        self._router.set_context(
                            ml_projection=self._last_ml,
                            session_data=session_state.get("data", {})
                        )
                        final_tactical = self._router.process_market_data(
                            df_live, asset=self.symbol, interval=self.interval,
                            macro_levels=self._macro_levels
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

    # ── Handlers auxiliares ───────────────────────────────────────────────────

    async def _handle_signals(self, tactical: dict):
        """Filtra, de-duplica y persiste señales en Supabase + Telegram (Signal Firewall)."""
        raw_signals = tactical.get("signals", [])
        inv_signals = tactical.get("invalidated_signals", []) # 💀 Auditoría de muerte
        
        ghost = get_ghost_state(self.symbol)
        
        # 1. Procesar Señales VIVAS
        approved, blocked_sigs = filter_signals_by_macro(raw_signals, ghost)
        
        # [ANTI-SPAM] Solo procesamos la señal más reciente de cada tipo para evitar ráfagas de historial
        def filter_latest_only(sigs):
            latest = {}
            for s in sigs:
                stype = str(s.get("type", "LONG")).upper()
                latest[stype] = s
            return list(latest.values())

        prospects_active = filter_latest_only(approved)
        prospects_blocked = filter_latest_only(blocked_sigs)

        now = time.time()

        # Procesamiento SECUENCIAL para evitar condiciones de carrera en Supabase
        for sig in prospects_active:
            sig_type = str(sig.get("type", "LONG")).upper()
            price = float(sig.get("price", 0))
            confluence = float(sig.get("confluence", {}).get("score", 0)) if sig.get("confluence") else 0

            if confluence < 15.0: continue

            # Cooldown local (10 minutos para el mismo precio)
            last = self._last_signals_sent.get(sig_type)
            if last:
                price_diff_pct = abs(price - last["price"]) / last["price"] if last["price"] > 0 else 1.0
                time_passed = now - last["ts"]
                if price_diff_pct < 0.001 and time_passed < 600:
                    continue

            print(f"[AUDIT] 🚀 Procesando señal {sig_type} para {self.symbol} (Confluencia: {confluence:.1f}%)")
            self._last_signals_sent[sig_type] = {"price": price, "ts": now}

            # Telegram (Solo si es fresca)
            ok_to_send, reason = signal_filter.should_send(self.symbol, sig)
            if ok_to_send:
                asyncio.create_task(send_signal_async(
                    signal=sig, asset=self.symbol,
                    regime=tactical.get("market_regime", "UNKNOWN"),
                    strategy=tactical.get("active_strategy", "N/A")
                ))

            # Supabase (AWAIT crítico para el motor de evolución)
            await self._persist_signal(sig, tactical, status="ACTIVE")
        
        for sig in prospects_blocked:
            await self._persist_signal(sig, tactical, status="BLOCKED")

        # 2. Procesar Señales MUERTAS (Solo la más relevante)
        latest_inv = filter_latest_only(inv_signals)
        for sig in latest_inv:
            confluence = float(sig.get("confluence", {}).get("score", 0)) if sig.get("confluence") else 0
            if confluence >= 15.0:
                raw_reason = str(sig.get('death_reason', 'INVALIDATED')).upper()
                safe_status = "COMPLETED" if "PROFIT" in raw_reason else "INVALIDATED"
                await self._persist_signal(sig, tactical, status=safe_status)

    async def _persist_signal(self, sig: dict, tactical: dict, status: str = "ACTIVE"):
        """Inserta la señal en public.signal_events con service_role key y fallback resiliente."""
        if not supabase_service:
            print("[SUPABASE] ⚠️ Cliente no disponible para persistencia.")
            return

        try:
            ghost = get_ghost_state(self.symbol)
            data = {
                "asset": self.symbol,
                "interval": "15m",
                "signal_type": str(sig.get("type", sig.get("signal_type", "LONG"))).upper(),
                "entry_price": float(sig.get("price", sig.get("entry_price", 0))),
                "stop_loss": float(sig.get("stop_loss", 0)),
                "take_profit": float(sig.get("take_profit_3r", sig.get("take_profit", 0))),
                "confluence_score": float((sig.get("confluence") or {}).get("score", sig.get("confluence_score", 0))),
                "regime": tactical.get("market_regime", "UNKNOWN"),
                "strategy": tactical.get("active_strategy", "N/A"),
                "trigger": sig.get("trigger", "GENERIC_SIGNAL"),
                "status": status,
                "metadata": {
                    "reasoning": tactical.get("confluence", {}).get("reasoning", ""),
                    "blocked_reason": sig.get("blocked_reason"),
                    "ghost_bias": ghost.macro_bias,
                    "fear_greed": ghost.fear_greed_value,
                    "death_reason": sig.get("death_reason")
                }
            }

            # Normalización de tipo
            if "LONG" in data["signal_type"]: data["signal_type"] = "LONG"
            elif "SHORT" in data["signal_type"]: data["signal_type"] = "SHORT"

            # [AUDIT-SUPABASE] 🕵️ Motor de Ciclo de Vida de Señal (Evolución y Cierre)
            try:
                lookback = supabase_service.table("signal_events").select("id, status, entry_price")\
                    .eq("asset", self.symbol)\
                    .eq("signal_type", data["signal_type"])\
                    .order("created_at", desc=True).limit(1).execute()
                
                if lookback.data:
                    last = lookback.data[0]
                    last_status = str(last["status"]).upper()
                    
                    # 1. ESCENARIO: EVOLUCIÓN (Sigue activa o sigue bloqueada)
                    if (last_status == "ACTIVE" and status == "ACTIVE") or \
                       (last_status == "BLOCKED" and status == "BLOCKED"):
                        
                        price_diff = abs(data["entry_price"] - last["entry_price"]) / last["entry_price"] if last["entry_price"] > 0 else 1.0
                        
                        # Si el precio es similar (< 0.5%), actualizamos la existente para no llenar la DB
                        if price_diff < 0.005: 
                            print(f"[AUDIT] 🧬 Evolucionando Tesis ({self.symbol}) - Status: {status}...")
                            upd_data = {
                                "entry_price": data["entry_price"],
                                "stop_loss": data["stop_loss"],
                                "take_profit": data["take_profit"],
                                "metadata": data.get("metadata")
                            }
                            try:
                                supabase_service.table("signal_events").update(upd_data).eq("id", last["id"]).execute()
                            except Exception as e_upd:
                                if "metadata" in str(e_upd) or "PGRST204" in str(e_upd):
                                    if "metadata" in upd_data: del upd_data["metadata"]
                                    supabase_service.table("signal_events").update(upd_data).eq("id", last["id"]).execute()
                            return

                    # 2. ESCENARIO: CIERRE (De Activa a cualquier otro estado muerto)
                    elif last_status == "ACTIVE" and status != "ACTIVE":
                        print(f"[AUDIT] 🏁 Cerrando señal activa en {self.symbol}. Motivo: {status}")
                        upd_data = {"status": status, "metadata": data.get("metadata")}
                        try:
                            supabase_service.table("signal_events").update(upd_data).eq("id", last["id"]).execute()
                        except Exception as e_upd:
                            if "metadata" in str(e_upd) or "PGRST204" in str(e_upd):
                                if "metadata" in upd_data: del upd_data["metadata"]
                                supabase_service.table("signal_events").update(upd_data).eq("id", last["id"]).execute()
                        return

            except Exception as e:
                print(f"[AUDIT] ⚠️ Error en motor de ciclo de vida (No bloqueante): {e}")

            # [AUDIT-SUPABASE] 🚀 Inserción de Nueva Señal (Solo si no hubo evolución/cierre previo)
            try:
                print(f"[AUDIT] 🆕 Creando nueva entrada de señal para {self.symbol} (Status: {status})")
                result = supabase_service.table("signal_events").insert(data).execute()
                if result.data:
                    print(f"[AUDIT] 💎 EXITO: Nueva señal persistida con ID: {result.data[0].get('id')}")
            except Exception as e_inner:
                # 🛑 FALLBACK: Migration 003 (Columna metadata)
                error_str = str(e_inner)
                if "metadata" in error_str or "PGRST204" in error_str:
                    print(f"[AUDIT] ⚠️ Reintentando sin 'metadata' por posible falta de columna en DB...")
                    if "metadata" in data: del data["metadata"]
                    supabase_service.table("signal_events").insert(data).execute()
                else:
                    raise e_inner

        except Exception as e:
            print(f"[SUPABASE] 🔴 Error CRÍTICO al persistir señal en {self.symbol}: {e}")

    async def _emit_advisor(self, tactical: dict, session_state: dict):
        """Llama al LLM Advisor y broadcast el resultado."""
        print(f"[BROADCASTER] 🧠 Iniciando análisis LLM para {self.symbol}...")
        try:
            # Enviar estado de 'Cargando' explícito si es necesario (opcional)
            # await self._broadcast({"type": "advisor_update", "data": "ANALIZANDO... ⚡"})

            # Timeout de 20 segundos para no colgar el worker
            advice = await asyncio.wait_for(
                generate_tactical_advice(self.symbol, 
                    tactical_data=tactical,
                    current_session=session_state.get("data", {}).get("current_session", "UNKNOWN"),
                    ml_projection=self._last_ml
                ),
                timeout=20.0
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

    async def _refresh_ghost(self):
        """Refresca Ghost Data y broadcast."""
        try:
            ghost = await refresh_ghost_data(self.symbol)
            await self._broadcast({"type": "ghost_update", "data": {
                "fear_greed_value": ghost.fear_greed_value,
                "fear_greed_label": ghost.fear_greed_label,
                "btc_dominance":    ghost.btc_dominance,
                "funding_rate":     ghost.funding_rate,
                "macro_bias":       ghost.macro_bias,
                "block_longs":      ghost.block_longs,
                "block_shorts":     ghost.block_shorts,
                "reason":           ghost.reason,
                "last_updated":     ghost.last_updated,
            }})
        except Exception as e:
            print(f"[BROADCASTER] {self._key} → Ghost refresh error: {e}")

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
# Main Execution (Standalone Worker)
# ──────────────────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="Slingshot Symbol Worker")
    parser.add_argument("symbol", type=str, help="Binance Symbol (e.g. BTCUSDT)")
    parser.add_argument("--interval", type=str, default="15m", help="Candle interval (default: 15m)")
    args = parser.parse_args()

    symbol = args.symbol.upper()
    interval = args.interval

    print(f"🚀 Iniciando SymbolWorker para {symbol} ({interval})...")
    redis_pool = redis.from_url(settings.REDIS_URL, decode_responses=True)

    worker = SymbolWorker(symbol, interval, redis_pool)
    await worker.start()

    # Mantener el proceso vivo
    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        pass
    except asyncio.CancelledError:
        pass
    finally:
        print(f"🛑 Apagando SymbolWorker para {symbol}...")
        await worker.stop()
        await redis_pool.aclose()

if __name__ == "__main__":
    try:
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Worker detenido manualmente.")
