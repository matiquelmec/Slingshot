import asyncio
import time
import pandas as pd
import traceback
from engine.core.logger import logger
from engine.core.store import store
from engine.api.config import settings
from engine.api.registry import registry
from engine.router.processors import StreamProcessor
from engine.indicators.onchain_provider import get_onchain_summary
from engine.api.json_utils import sanitize_for_json

class BroadcasterPipeline:
    """
    Gestiona la ejecución de los pipelines Fast Path (ticks) y Slow Path (cierre de vela).
    """
    def __init__(self, state, router, broadcaster):
        self.state = state
        self.router = router
        self.bc = broadcaster  # Referencia para broadcast y emit_advisor

    async def execute_fast_path(self, candle_payload: dict, raw_data: dict, force: bool = False):
        """Pipeline de baja latencia (Alpha Pipeline v10.2)."""
        try:
            now = time.time()
            pulse_interval = settings.PRIORITY_TIERS.get(self.state.symbol, settings.DEFAULT_PULSE_INTERVAL)
            
            # Diagnostic: Log every tick arrival
            logger.debug(f"[TICK] {self.state.symbol} arrived")

            regime = self.state.last_tactical.get("data", {}).get("market_regime", "UNKNOWN") if self.state.last_tactical else "UNKNOWN"
            if regime in ["CHOPPY", "ACCUMULATION", "DISTRIBUTION"]:
                pulse_interval = max(pulse_interval, 3.0) 
            
            if not force and (now - self.state.last_pulse_ts < pulse_interval):
                return
                
            self.state.last_pulse_ts = now
            latency_ms = (now * 1000) - raw_data.get("data", {}).get("E", now * 1000)
            
            logger.info(f"[PIPELINE] 🚀 Ejecutando Fast Path para {self.state.symbol}")
            current_buffer = [i["data"] for i in self.state.live_buffer] + [candle_payload["data"]]
            df_live = pd.DataFrame(current_buffer)
            
            delta_fast = await StreamProcessor.process_fast_path(
                symbol=self.state.symbol, interval=self.state.interval,
                candle_payload=candle_payload, ws_data=raw_data,
                context={"df_live": df_live, "avg_volume": getattr(store, 'get_avg_volume', lambda x: 0)(self.state.symbol)}
            )

            registry.record_latency(self.state.symbol, delta_fast.get("latency_ms", 0))

            if delta_fast.get("latency_dirty"):
                await self.bc._broadcast({"type": "neural_log", "data": {"type": "SYSTEM", "message": f"⚠️ LATENCY_DIRTY: {delta_fast['latency_ms']}ms"}})
            
            if delta_fast.get("event") == "ABSORPTION_ALERT":
                logger.warning(f"[PIPELINE] 🚨 ABSORCIÓN detectada en {self.state.symbol}")
                await self.bc._broadcast({"type": "absorption_alert", "data": {"rvol": delta_fast.get('rvol', 0)}})
                from engine.core.session_manager import SessionManager
                asyncio.create_task(self.bc._emit_advisor(self.state.last_tactical or {}, SessionManager.get_global_session_status(), is_absorption_alert=True))

            ml_data = delta_fast.get("ml_prediction", {})
            if ml_data:
                self.state.ml_projection = ml_data
                prob_raw = ml_data.get("probability", 50)
                prob_bull = prob_raw if ml_data.get("direction") == "ALCISTA" else 100 - prob_raw
                self.state.ema_ml_prob = (prob_bull * 0.2) + (self.state.ema_ml_prob * 0.8) # Alpha fijo 0.2

            drift_ms = delta_fast.get("latency_ms", 0)
            if drift_ms > 5000:
                logger.warning(f"⚠️ [LATENCY] Drift crítico ({drift_ms:.2f}ms). Saltando update táctico para {self.state.symbol}")
                return

            try:
                live_tactical = await self.router.process_market_data(
                    df_live, asset=self.state.symbol, interval=self.state.interval,
                    macro_levels=getattr(self.bc, '_macro_levels', None), htf_bias=self.state.htf_bias, 
                    heatmap=self.state.heatmap, silent=True,
                    event_time_ms=raw_data.get("data", {}).get("E"),
                    smc_data=getattr(self.bc, '_persistent_smc', None)
                )
                self.state.last_tactical = {"data": live_tactical}
                self.state.live_rvol = float((live_tactical.get('diagnostic') or {}).get('rvol', 0))
                
                for sig in live_tactical.get("signals", []):
                    await self.bc._broadcast({"type": "signal_auditor_update", "data": sig})

                for sig in live_tactical.get("blocked_signals", []):
                    await self.bc._broadcast({"type": "signal_auditor_update", "data": sig})

                await self.bc._broadcast({"type": "tactical_update", "data": live_tactical})
            except Exception as e:
                logger.error(f"[FAST-PATH] Pipeline tactical error: {e}")

            await self.bc._broadcast({
                "type": "neural_pulse",
                "data": {
                    "ml_projection": self.state.ml_projection, 
                    "liquidity_heatmap": self.state.heatmap, 
                    "latency_ms": delta_fast.get("latency_ms", 0), 
                    "rvol_live": self.state.live_rvol
                }
            })

            # 🚀 [REAL-TIME] Sincronización de Sesiones (Niveles y Killzones)
            is_closed = candle_payload.get("data", {}).get("closed", False)
            session_update = self.bc._session_manager.update(candle_payload, is_closed=is_closed)
            if "data" in session_update:
                session_update["data"]["asset"] = self.state.symbol
                
            self.state.last_session = session_update
            await self.bc._broadcast(session_update)
            
            # 6. 🕒 DISPARADOR DE SLOW PATH (Cierre de Vela)
            if is_closed:
                asyncio.create_task(self.execute_slow_path(candle_payload))

            # 7. 📡 METRICA FINAL
            registry.record_latency(self.state.symbol, latency_ms)
            
        except Exception as e:
            logger.error(f"🚨 [PIPELINE-FATAL] Error en Fast Path {self.state.symbol}: {e}")
            logger.error(traceback.format_exc())

    async def execute_slow_path(self, candle_payload: dict):
        """Lógica de cierre de vela (Strategy Delta Δ)."""
        self.state.live_buffer.append(candle_payload)
        self.state.candle_closes += 1
        
        delta_slow = await StreamProcessor.process_slow_path(
            symbol=self.state.symbol, candle_payload=candle_payload,
            live_buffer=list(self.state.live_buffer), 
            persistent_smc=getattr(self.bc, '_persistent_smc', None),
            context={"candle_closes": self.state.candle_closes, "ml_direction": self.state.ml_projection.get("direction", "NEUTRAL")}
        )

        if delta_slow.get("smc_data"):
            setattr(self.bc, '_persistent_smc', delta_slow["smc_data"])
            await self.bc._broadcast({"type": "smc_data", "data": delta_slow["smc_data"]})

        if delta_slow.get("liquidation_clusters"):
            await store.update_liquidation_clusters(self.state.symbol, delta_slow["liquidation_clusters"])
            await self.bc._broadcast({"type": "liquidation_update", "data": delta_slow["liquidation_clusters"]})

        # 3. Notificar Cierre de Vela al SessionManager (Persistencia)
        self.bc._session_manager.update(candle_payload, is_closed=True)

        try:
            df_slow = pd.DataFrame([i["data"] for i in self.state.live_buffer])
            df_slow["timestamp"] = pd.to_datetime(df_slow["timestamp"], unit="s")

            news_items = await store.get_news()
            econ_events = await store.get_economic_events(limit=5)
            
            # SMT Divergence logic
            correlated_df = await self._get_correlated_df()
            
            # Update HTF Bias
            bias = await store.get_htf_bias(self.state.symbol)
            if bias:
                self.state.htf_bias = bias
            
            self.router.set_context(
                ml_projection=self.state.ml_projection, 
                session_data=(self.state.last_session or {}).get("data", {}),
                news_items=news_items, economic_events=econ_events, 
                liquidation_clusters=delta_slow.get("liquidation_clusters", []),
                correlated_df=correlated_df, ghost_data=self.state.last_ghost
            )
            
            final_tactical = await self.router.process_market_data(
                df_slow, asset=self.state.symbol, interval=self.state.interval,
                macro_levels=getattr(self.bc, '_macro_levels', None), htf_bias=self.state.htf_bias, silent=False
            )
            await self.bc._broadcast({"type": "tactical_update", "data": final_tactical})
            await self.bc._handle_signals(final_tactical, silent=False)

            current_candle_ts = str(candle_payload["data"]["timestamp"])
            if current_candle_ts != str(self.state.last_advisor_ts):
                self.state.last_advisor_ts = current_candle_ts
                
                # 🛡️ Regla de Throttling IA v11.5: Activar LLM solo ante detonantes cuantitativos
                conf_score = final_tactical.get("confluence_score", 0) if isinstance(final_tactical, dict) else 0
                has_active_signal = isinstance(final_tactical, dict) and final_tactical.get("signal_type", "NONE") != "NONE"
                
                if conf_score >= 70 or has_active_signal:
                    logger.info(f"[ADVISOR_TRIGGER] ⚡ Evento detonante cuantitativo para {self.state.symbol} (Score: {conf_score}%). Invocando LLM Contextual.")
                    from engine.core.session_manager import SessionManager
                    asyncio.create_task(self.bc._emit_advisor(final_tactical, SessionManager.get_global_session_status()))
                else:
                    logger.debug(f"[ADVISOR_TRIGGER] ⏸️ Gatekeeping de vela para {self.state.symbol}. Motivo: Confluencia {conf_score}% sin señal activa.")

        except Exception as e:
            logger.error(f"[SLOW-PATH] tactical error: {e}")

    async def _get_correlated_df(self):
        mirror_asset = "ETHUSDT" if self.state.symbol in ["BTCUSDT", "SOLUSDT"] else "BTCUSDT"
        from engine.api.registry import registry
        mirror_broadcaster = registry.get_broadcaster(mirror_asset, self.state.interval)
        
        if mirror_broadcaster and len(mirror_broadcaster._live_buffer) > 0:
            try:
                df = pd.DataFrame([i["data"] for i in mirror_broadcaster._live_buffer])
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
                return df
            except Exception as e:
                logger.error(f"[PIPELINE] Error SMT: {e}")
        return None
