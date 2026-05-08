"""
ws_manager.py — SymbolBroadcaster v10.1.0 (Modular Refactor)
=========================================================
Arquitectura: "Compute Once, Fan-Out N"
Módulos Refactorizados:
  - broadcaster/state.py      → Gestión de estado y caché
  - broadcaster/dispatcher.py → Distribución y sincronización
  - broadcaster/pipeline.py   → Ejecución de Fast/Slow path
"""

import asyncio
import time
import traceback
import pandas as pd
import websockets as ws_client
try:
    import orjson as json
except ImportError:
    import json

from engine.api.config import settings
from engine.core.store import store
from engine.api.registry import registry
from engine.core.logger import logger
from engine.core.session_manager import SessionManager
from engine.router.processors import StreamProcessor
from engine.main_router import SlingshotRouter
from engine.indicators.data_utils import fetch_binance_history
from engine.indicators.structure import (
    identify_order_blocks, extract_smc_coordinates,
    identify_support_resistance, get_key_levels, consolidate_mtf_levels
)
from engine.indicators.liquidations import estimate_liquidation_clusters
from engine.indicators.liquidity import analyze_neural_heatmap
from engine.indicators.onchain_provider import get_onchain_summary, refresh_symbol_onchain

# Componentes Modulares
from engine.api.broadcaster.state import BroadcasterState
from engine.api.broadcaster.dispatcher import BroadcasterDispatcher
from engine.api.broadcaster.pipeline import BroadcasterPipeline
from engine.api.broadcaster.rest_fallback import BitunixFallback
from engine.api.signal_handler import SignalHandler
from engine.api.advisor_bridge import AdvisorBridge

class SymbolBroadcaster:
    """
    Mantiene UNA conexión Binance WS por símbolo+intervalo y distribuye
    todos los mensajes a N clientes simultáneos.
    """

    def __init__(self, symbol: str, interval: str, persistent: bool = False):
        self.symbol = symbol.upper()
        self.interval = interval
        self.persistent = persistent
        self._key = f"{self.symbol}:{self.interval}"
        self._last_tick_ts = time.time()

        # 1. Estado y Componentes
        self.state = BroadcasterState(self.symbol, self.interval)
        self._subscribers: dict = {}
        self._lock = asyncio.Lock()
        self._task = None

        self._router = SlingshotRouter()
        self._session_manager = SessionManager(symbol=self.symbol)
        
        self.dispatcher = BroadcasterDispatcher(self.state, self._subscribers, self._lock, self)
        self.pipeline = BroadcasterPipeline(self.state, self._router, self)
        
        self._signal_handler = SignalHandler(self.symbol, self.interval, self)
        self._advisor_bridge = AdvisorBridge(self.symbol, self.interval, self)
        self.fallback = BitunixFallback(self.symbol, self.interval, self)
        self._store = store

        # Propiedades de compatibilidad para evitar romper módulos externos
        self._macro_levels = None
        self._persistent_smc = None

        logger.info(f"[BROADCASTER] ✅ Inicializado (Modular v10.1): {self._key}")

    # --- Compatibilidad de Propiedades (Getters & Setters para Bridges) ---
    @property
    def _live_buffer(self): return self.state.live_buffer
    @property
    def _history(self): return self.state.history
    
    @property
    def _last_ghost(self): return self.state.last_ghost
    @_last_ghost.setter
    def _last_ghost(self, val): self.state.last_ghost = val

    @property
    def _last_smc(self): return self.state.last_smc
    @_last_smc.setter
    def _last_smc(self, val): self.state.last_smc = val

    @property
    def _last_tactical(self): return self.state.last_tactical
    @_last_tactical.setter
    def _last_tactical(self, val): self.state.last_tactical = val

    @property
    def _last_session(self): return self.state.last_session
    @_last_session.setter
    def _last_session(self, val): self.state.last_session = val

    @property
    def _last_advisor(self): return self.state.last_advisor
    @_last_advisor.setter
    def _last_advisor(self, val): self.state.last_advisor = val

    @property
    def _last_liquidations(self): return self.state.last_liquidations
    @_last_liquidations.setter
    def _last_liquidations(self, val): self.state.last_liquidations = val

    @property
    def _last_onchain(self): return self.state.last_onchain
    @_last_onchain.setter
    def _last_onchain(self, val): self.state.last_onchain = val

    @property
    def _htf_bias(self): return self.state.htf_bias
    @_htf_bias.setter
    def _htf_bias(self, val): self.state.htf_bias = val

    @property
    def _live_rvol(self): return self.state.live_rvol
    @_live_rvol.setter
    def _live_rvol(self, val): self.state.live_rvol = val

    @property
    def _last_ml(self): return self.state.ml_projection
    @_last_ml.setter
    def _last_ml(self, val): self.state.ml_projection = val

    @property
    def latest_price(self): return self.state.latest_price

    # --- Suscripción ---
    async def subscribe(self, client_id: str) -> asyncio.Queue:
        queue = asyncio.Queue(maxsize=200)
        async with self._lock:
            self._subscribers[client_id] = queue
        
        logger.info(f"[BROADCASTER] {self._key} → +cliente {client_id[:6]}")

        # Hidratación inicial
        history_to_send = list(self.state.live_buffer) if self.state.live_buffer else self.state.history
        if history_to_send:
            await queue.put({"type": "history", "data": history_to_send})
        
        # Sync Radar & Signals
        all_active_signals = await store.get_signals()
        for sig in list(all_active_signals)[-30:]:
            if sig.get("status") in ["PENDING", "ACTIVE", "FILLED"]:
                await queue.put({"type": "signal_auditor_update", "data": sig})

        if registry._last_radar_summary:
            await queue.put({"type": "radar_update", "data": registry._last_radar_summary})

        # Cache recovery
        for state_msg in [self.state.last_ghost, self.state.last_smc, self.state.last_tactical, 
                         self.state.last_session, self.state.last_advisor, self.state.last_liquidations, 
                         self.state.last_onchain, self.state.last_htf_bias_msg]:
            if state_msg: await queue.put(state_msg)

        return queue

    async def unsubscribe(self, client_id: str):
        async with self._lock:
            self._subscribers.pop(client_id, None)
        logger.info(f"[BROADCASTER] {self._key} → -cliente {client_id[:6]}")

    def subscriber_count(self) -> int:
        return len(self._subscribers)


    async def _broadcast(self, message: dict):
        await self.dispatcher.broadcast(message)

    # --- Ciclo de Vida ---
    async def start(self):
        if self._task and not self._task.done(): return
        self._task = asyncio.create_task(self._run(), name=f"broadcaster-{self._key}")

    async def stop(self):
        if self._task and not self._task.done():
            self._task.cancel()
            try: await self._task
            except asyncio.CancelledError: pass
        logger.info(f"[BROADCASTER] 🛑 Detenido: {self._key}")

    async def _run(self):
        retry_delay = 2.0
        while True:
            try:
                await self._bootstrap()
                # Intentar conectar con un timeout agresivo para el handshake
                await asyncio.wait_for(self._stream_live(), timeout=None) # El loop interno tiene sus propios timeouts
                retry_delay = 2.0
            except (asyncio.TimeoutError, Exception) as e:
                logger.error(f"[BROADCASTER] Error o Timeout en {self._key}: {e}")
                
                # [FALLBACK] Forzamos el inicio del rescate si no logramos conectar en 10s
                if not self.state.is_connected:
                    logger.warning(f"⚠️ [BROADCASTER] {self._key} Sin conexión Binance. Activando Bitunix...")
                    await self.fallback.start()
                
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60.0)

    # --- Bootstrap ---
    async def _bootstrap(self):
        logger.info(f"[BROADCASTER] {self._key} → Iniciando Bootstrap Progresivo...")
        try:
            history = await fetch_binance_history(self.symbol, self.interval, limit=300)
            if history:
                self.state.history = history
                self.state.live_buffer.extend(history[-300:])
                await self._broadcast({"type": "history", "data": history})
                
                # 4. Bootstrap de Indicadores Estructurales
                self._session_manager.bootstrap(history)
                
                # Lightning SMC & Initial Liquidations
                try:
                    df_fast = pd.DataFrame([i["data"] for i in history[-100:]]) # Use last 100 for pivots
                    df_fast["timestamp"] = pd.to_datetime(df_fast["timestamp"], unit="s")
                    
                    # SMC
                    fast_smc = extract_smc_coordinates(identify_order_blocks(df_fast))
                    await self._broadcast({"type": "smc_data", "data": fast_smc})
                    
                    # Initial Liquidations
                    latest_price = float(history[-1]["data"]["close"])
                    initial_liqs = estimate_liquidation_clusters(df_fast, latest_price)
                    if initial_liqs:
                        await store.update_liquidation_clusters(self.symbol, initial_liqs)
                        liq_msg = {"type": "liquidation_update", "data": initial_liqs}
                        await self._broadcast(liq_msg)
                        self.state.last_liquidations = liq_msg # Cache full message for new subs
                except Exception as smc_e:
                    logger.debug(f"[BOOTSTRAP] Error en Initial Analysis ({self.symbol}): {smc_e}")
        except Exception as e:
            logger.error(f"[BOOTSTRAP] Error en carga crítica: {e}")

        # 🚀 [HYDRATION v10.2] Sincronización Inicial de Telemetría
        asyncio.create_task(self._sync_initial_telemetry())
        
        asyncio.create_task(self._load_background_data())

    async def _sync_initial_telemetry(self):
        """Asegura que el cliente reciba datos macro y de sesión inmediatamente."""
        try:
            # 1. Sincronizar Sesión
            session_payload = self._session_manager.get_current_state()
            self.state.last_session = session_payload
            await self._broadcast(session_payload)
            
            # 2. Sincronizar Ghost & On-Chain (vía Bridge)
            await self._advisor_bridge.refresh_ghost()

            # 3. Análisis Táctico Inicial (One-Shot)
            if self.state.history:
                last_candle = self.state.history[-1]
                await self.pipeline.execute_fast_path(last_candle, {"data": {"E": int(time.time()*1000)}}, force=True)
            
            logger.info(f"[BROADCASTER] 🚀 {self._key} Telemetría inicial sincronizada.")
        except Exception as e:
            logger.error(f"[BROADCASTER] ⚠️ Error en telemetría inicial {self._key}: {e}")

    async def _load_background_data(self):
        try:
            await asyncio.sleep(1.0)
            # Carga Macro & Indicadores Pesados
            h4_raw = await fetch_binance_history(self.symbol, "4h", limit=250)
            h1_raw = await fetch_binance_history(self.symbol, "1h", limit=250)
            
            if h1_raw and h4_raw:
                def _get_levels(raw, tf):
                    df = pd.DataFrame([i["data"] for i in raw])
                    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
                    return get_key_levels(identify_support_resistance(df, interval=tf))

                self._macro_levels = consolidate_mtf_levels(_get_levels(h1_raw, "1h"), _get_levels(h4_raw, "4h"), 3)
            
            # Refrescar bias inicial y enviar a clientes conectados
            bias = await store.get_htf_bias(self.symbol)
            if bias:
                self.state.htf_bias = bias
                bias_dict = bias.to_dict() if hasattr(bias, 'to_dict') else (bias if isinstance(bias, dict) else {})
                bias_dict["symbol"] = self.symbol
                htf_msg = {"type": "htf_bias_update", "data": bias_dict}
                self.state.last_htf_bias_msg = htf_msg
                await self._broadcast(htf_msg)
                logger.info(f"[BROADCASTER] {self.symbol} → HTF Bias hidratado y propagado: {bias_dict.get('direction', 'N/A')}")
            logger.info(f"[BROADCASTER] {self.symbol} → Background data hydrated.")
        except Exception as e:
            logger.error(f"[BG-DATA] Error: {e}")

    # --- Stream En Vivo ---
    async def _stream_live(self):
        kline_stream = f"{self.symbol.lower()}@kline_{self.interval}"
        depth_stream = f"{self.symbol.lower()}@depth20@100ms"
        # Enrutamiento Unificado de Alta Resiliencia
        # Forzamos Spot WS (9443) para TODOS los activos debido a bloqueos regionales/ISP
        # en fstream.binance.com que causan 'handshake timeout' o silencian streams de velas.
        # El precio Spot vs Futures Perps difiere <0.01%, estadísticamente irrelevante para SMC.
        base_ws_url = "wss://stream.binance.com:9443"
        binance_url = f"{base_ws_url}/stream?streams={kline_stream}/{depth_stream}"

        logger.info(f"[BROADCASTER] {self._key} → Iniciando túnel (Unified Spot Routing): {binance_url}")
        
        try:
            # Correcto: await wait_for devuelve el context manager, luego entramos con async with
            async with await asyncio.wait_for(ws_client.connect(binance_url, ping_interval=30), timeout=15.0) as binance_ws:
                self.state.is_connected = True
                logger.info(f"[BROADCASTER] {self._key} → Stream Conectado 🟢")
                
                # Si el fallback estaba corriendo, lo detenemos
                await self.fallback.stop()
                self._last_tick_ts = time.time()

                while self.state.is_connected:
                    try:
                        raw = await asyncio.wait_for(binance_ws.recv(), timeout=15.0)
                        self._last_tick_ts = time.time()
                        data = json.loads(raw)
                        stream_type = data.get("stream", "")
                        payload = data.get("data", {})
                        
                        if "depth" in stream_type:
                            await self._process_depth_stream(payload)
                        elif "kline" in stream_type:
                            await self._process_kline_stream(payload, data)
                    except asyncio.TimeoutError:
                        logger.warning(f"[BROADCASTER] Timeout de datos en {self._key}. Reintentando...")
                        break
        except Exception as e:
            logger.error(f"[BROADCASTER] Fallo crítico de conexión en {self._key}: {e}")
            raise

    async def _process_depth_stream(self, payload: dict):
        price = self.latest_price or 1.0
        self.state.heatmap = analyze_neural_heatmap(
            bids=payload.get("bids") or payload.get("b", []),
            asks=payload.get("asks") or payload.get("a", []),
            current_price=price
        )
        self.state.liquidity = {
            "bids": [{"price": b["price"], "volume": b["volume"]} for b in self.state.heatmap.get("hot_bids", [])],
            "asks": [{"price": a["price"], "volume": a["volume"]} for a in self.state.heatmap.get("hot_asks", [])]
        }
        
        now = time.time()
        if now - getattr(self, '_last_heatmap_ts', 0) > 1.0:
            self._last_heatmap_ts = now
            await self._broadcast({
                "type": "neural_pulse",
                "data": {
                    "ml_projection": self.state.ml_projection, 
                    "liquidity_heatmap": self.state.heatmap,
                    "rvol_live": self.state.live_rvol
                }
            })

    async def _process_kline_stream(self, payload: dict, raw_data: dict):
        kline = payload.get("k")
        if not kline: return
        
        # 🟢 Sync Latest Price — escribir en el STATE, no en el broadcaster
        self.state.latest_price = float(kline["c"])

        candle = {
            "type": "candle",
            "data": {
                "timestamp": kline["t"] / 1000, "open": float(kline["o"]),
                "high": float(kline["h"]), "low": float(kline["l"]),
                "close": float(kline["c"]), "volume": float(kline["v"]),
            }
        }
        await self._broadcast(candle)

        # 🚀 [ULTRA-LOW LATENCY] Procesamiento en segundo plano para no bloquear el siguiente TICK
        from engine.execution.omega_listener import omega_centinel
        asyncio.create_task(omega_centinel.check_live_price(self.symbol, float(kline["c"]), self))
        asyncio.create_task(self.pipeline.execute_fast_path(candle, raw_data))

        if kline.get("x", False):
            # El Slow Path SÍ se espera porque es crítico para el cambio de vela
            await self.pipeline.execute_slow_path(candle)

    # --- Handlers Auxiliares (Wrappers para compatibilidad) ---
    async def _handle_signals(self, tactical: dict, silent: bool = False):
        await self._signal_handler.handle(tactical, silent=silent)

    async def _emit_advisor(self, tactical: dict, session: dict, is_absorption_alert: bool = False):
        await self._advisor_bridge.emit(tactical, session, is_absorption_alert=is_absorption_alert)

    async def _persist_signal(self, sig: dict, tactical: dict, **kwargs):
        await self._signal_handler.persist(sig, tactical, **kwargs)
