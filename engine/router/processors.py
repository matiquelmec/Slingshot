import asyncio
import time
import pandas as pd
import traceback
from typing import Dict, Optional, Any
from engine.core.logger import logger
from engine.api.config import settings
from engine.ml.inference import ml_engine
from engine.ml.drift_monitor import drift_monitor
from engine.ml.features import FeatureEngineer
from engine.indicators.structure import (
    identify_order_blocks, extract_smc_coordinates, 
    merge_smc_states, mitigate_smc_state
)
from engine.indicators.liquidations import estimate_liquidation_clusters
from engine.indicators.ghost_data import get_ghost_state
from engine.core.session_manager import SessionManager
from engine.core.store import store

class StreamProcessor:
    """
    Motor especializado de procesamiento (Strategy Delta Δ).
    Desacopla la lógica de 'Fast Path' (ticks) y 'Slow Path' (velas cerradas)
    del gestor de WebSockets (ws_manager.py).
    """

    @staticmethod
    async def process_fast_path(
        symbol: str, 
        interval: str, 
        candle_payload: dict, 
        ws_data: dict,
        context: dict
    ) -> Dict[str, Any]:
        """
        Analiza cada tick individual (FAST PATH).
        Misión: Latencia ultra-baja y detección de anomalías (Absorption/Whales).
        """
        try:
            # 1. ⚠️ CHECK DE LATENCIA (Ruta Magallánica / Punta Arenas)
            # Si el tick tarda > 800ms en llegar desde Binance (E) hasta aquí, marcar como DIRTY.
            event_time = ws_data.get("data", {}).get("E")
            latency_ms = 0
            is_latency_dirty = False
            
            if event_time:
                now_ms = int(time.time() * 1000)
                latency_ms = now_ms - event_time
                if latency_ms > 800:
                    is_latency_dirty = True
                    logger.debug(f"[DELTA] 🐢 Tick Latency Dirty: {latency_ms}ms para {symbol}")

            # 2. 🐋 WHALE SENSOR & ABSORPTION (v6.0 Intel)
            # Detectar anomalías de volumen inter-vela antes de que cierre.
            latest_candle = candle_payload.get("data", {})
            fast_rvol = 0.0
            avg_vol = context.get("avg_volume", 0)
            
            if avg_vol > 0:
                fast_rvol = latest_candle.get("volume", 0) / avg_vol
                if fast_rvol >= 3.5:
                    return {
                        "event": "ABSORPTION_ALERT",
                        "rvol": round(fast_rvol, 2),
                        "latency_dirty": is_latency_dirty,
                        "latency_ms": latency_ms
                    }

            # 3. 🧠 ML INFERENCIA LIVE (High Priority)
            df_live = context.get("df_live")
            ml_pred = {}
            if df_live is not None and not df_live.empty:
                loop = asyncio.get_running_loop()
                ml_pred = await loop.run_in_executor(None, ml_engine.predict_live, df_live)

            return {
                "event": "FAST_TICK",
                "ml_prediction": ml_pred,
                "latency_dirty": is_latency_dirty,
                "latency_ms": latency_ms,
                "rvol": round(fast_rvol, 2)
            }

        except Exception as e:
            logger.error(f"[DELTA-CPU] Error en Fast Path ({symbol}): {e}")
            return {"event": "ERROR", "error": str(e)}

    @staticmethod
    async def process_slow_path(
        symbol: str, 
        candle_payload: dict,
        live_buffer: list,
        persistent_smc: dict,
        context: dict
    ) -> Dict[str, Any]:
        """
        Analiza el cierre de vela (SLOW PATH).
        Misión: Re-cómputo de estructura (SMC), Drift Monitoring y Liquidaciones.
        """
        try:
            # Re-construcción del DF para cálculos pesados
            df_live = pd.DataFrame([i["data"] for i in live_buffer])
            df_live["timestamp"] = pd.to_datetime(df_live["timestamp"], unit="s")
            
            # 1. 🏗️ RE-CÓMPUTO ESTRUCTURAL (SMC)
            # Offload a thread para no bloquear el Event Loop
            df_ob = await asyncio.to_thread(identify_order_blocks, df_live)
            smc_new = await asyncio.to_thread(extract_smc_coordinates, df_ob)
            
            # Mitigación y Merge
            current_low = float(candle_payload["data"]["low"])
            current_high = float(candle_payload["data"]["high"])
            if persistent_smc:
                mitigated = mitigate_smc_state(persistent_smc, current_low, current_high)
                updated_smc = merge_smc_states(mitigated, smc_new)
            else:
                updated_smc = smc_new

            # 2. 📈 LIQUIDACIONES (Trapped Money)
            latest_price = float(candle_payload["data"]["close"])
            liq_clusters = await asyncio.to_thread(estimate_liquidation_clusters, df_live, latest_price)

            # 3. 📈 DRIFT MONITORING (Accuracy & PSI)
            # Evaluamos la predicción anterior vs el cierre actual
            last_prediction = context.get("ml_direction")
            if last_prediction:
                actual_up = 1 if candle_payload["data"]["close"] > candle_payload["data"]["open"] else 0
                pred_up = 1 if last_prediction == "ALCISTA" else 0
                drift_monitor.record_prediction(pred_up, actual_up)

            # Check de Drift (cada 100 velas)
            candle_closes = context.get("candle_closes", 0)
            cleanup_event = None
            if candle_closes % 100 == 0:
                # Drift Watchdog
                fe = FeatureEngineer()
                df_features = await asyncio.to_thread(fe.generate_features, df_live.copy())
                asyncio.create_task(asyncio.to_thread(drift_monitor.check, df_features))
                cleanup_event = "CLEANUP_PERFORMED"

            return {
                "event": "CANDLE_CLOSE",
                "smc_data": updated_smc,
                "liquidation_clusters": liq_clusters,
                "cleanup_event": cleanup_event
            }

        except Exception as e:
            logger.error(f"[DELTA-CPU] Error en Slow Path ({symbol}): {e}")
            traceback.print_exc()
            return {"event": "ERROR", "error": str(e)}
