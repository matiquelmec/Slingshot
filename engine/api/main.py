from collections import deque
from pathlib import Path
import asyncio
import time
import json
import random

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import httpx
import pandas as pd
from datetime import datetime, timezone
import pytz
import websockets as ws_client

# ✅ Serializer robusto — resuelve Timestamp / numpy no serializables globalmente
from engine.api.json_utils import sanitize_for_json, SlingshotJSONEncoder

# Parchar WebSocket.send_json UNA VEZ aquí para que todos los send_json()
# del módulo usen el encoder correcto de forma transparente.
_original_send_json = WebSocket.send_json
async def _safe_send_json(self, data, mode="text"):
    """Wrapper que sanitiza cualquier tipo no serializable antes de enviar."""
    clean = sanitize_for_json(data)
    await _original_send_json(self, clean, mode=mode)
WebSocket.send_json = _safe_send_json  # type: ignore[method-assign]

# Importar el Enrutador Maestro del Engine
from engine.main_router import SlingshotRouter
from engine.api.config import settings

# 🔐 Session Manager (fuente de verdad de sesiones — sin DB, por símbolo)
from engine.core.session_manager import SessionManager as _SessionManager

# Dict de managers por símbolo para evitar cross-talk entre mercados
_session_managers: dict[str, _SessionManager] = {}

def get_session_manager(symbol: str) -> _SessionManager:
    """Retorna el SessionManager específico para cada símbolo."""
    key = symbol.upper()
    if key not in _session_managers:
        _session_managers[key] = _SessionManager(symbol=key)
    return _session_managers[key]

from engine.api.ws_manager import manager

# 💬 Notificaciones
from engine.notifications.telegram import send_signal_async, send_drift_alert_async
from engine.notifications.filter import signal_filter

# 🔮 Datos Fantasma (Nivel 1 - Filtro Macro)
from engine.indicators.ghost_data import refresh_ghost_data, get_ghost_state, filter_signals_by_macro, is_cache_fresh

# 🧠 Drift Monitor (Auto-supervisión del Modelo ML)
from engine.ml.drift_monitor import drift_monitor
from engine.ml.features import FeatureEngineer
from engine.ml.inference import ml_engine

# 🏗️ Estructura e Indicadores
from engine.indicators.structure import (
    identify_support_resistance,
    get_key_levels,
    identify_order_blocks,
    extract_smc_coordinates,
    consolidate_mtf_levels
)
from engine.indicators.liquidity import detect_liquidity_clusters

# 🧙‍♂️ Asesor Cuantitativo (LLM)
from engine.api.advisor import generate_tactical_advice


# NOTA: build_session_update() reemplazada por SessionManager (engine/core/session_manager.py)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Capa 4: Puente de Conectividad de Alta Velocidad para el Motor Cuantitativo",
    version=settings.VERSION,
)

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Iniciar el Cerebro del Motor
engine_router = SlingshotRouter()


async def fetch_binance_history(symbol: str, interval: str = "15m", limit: int = 200) -> list:
    """
    Descarga velas históricas recientes desde la API REST de Binance.
    Retorna una lista de dicts con formato estandarizado.
    """
    url = f"https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol.upper(), "interval": interval, "limit": limit}
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        raw = response.json()
    
    candles = []
    for k in raw:
        candles.append({
            "type": "candle",
            "data": {
                "timestamp": k[0] / 1000,  # Binance devuelve ms, lightweight-charts necesita segundos
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5]),
            }
        })
    return candles


@app.get("/")
async def root():
    return {
        "status": "online",
        "engine": "Slingshot Gen 1 (Criptodamus Heritage)",
        "version": settings.VERSION
    }

@app.get("/api/v1/analyze/{symbol}")
async def analyze_symbol(symbol: str, timeframe: str = "15m"):
    """
    Endpoint para que el Frontend solicite un análisis instantáneo de un activo.
    Cold-start inteligente: si no hay parquet local, descarga desde Binance REST
    y persiste en disco para que el engine pueda operar desde el primer request.
    """
    try:
        file_path = Path(__file__).parent.parent.parent / "data" / f"{symbol.lower()}_{timeframe}.parquet"

        if not file_path.exists():
            print(f"[ANALYZE] Cold-start detectado para {symbol} {timeframe}. Descargando desde Binance...")
            try:
                raw = await fetch_binance_history(symbol, interval=timeframe, limit=500)
                if not raw:
                    return {"error": f"Binance no devolvió datos para {symbol} en {timeframe}"}

                df_bootstrap = pd.DataFrame([item['data'] for item in raw])
                df_bootstrap['timestamp'] = pd.to_datetime(df_bootstrap['timestamp'], unit='s')

                # Persistir en disco para que las próximas llamadas sean instantáneas
                file_path.parent.mkdir(parents=True, exist_ok=True)
                df_bootstrap.to_parquet(file_path, index=False)
                print(f"[ANALYZE] Bootstrap completado: {len(df_bootstrap)} velas guardadas en {file_path.name}")
                data = df_bootstrap
            except Exception as fetch_err:
                return {
                    "error": f"No hay datos locales y Binance no está disponible: {fetch_err}",
                    "hint": "Verifica tu conexión o desactiva el VPN."
                }
        else:
            data = pd.read_parquet(file_path)

        result = engine_router.process_market_data(data, asset=symbol.upper(), interval=timeframe)
        # sanitize_for_json garantiza que el resultado sea 100% serializable
        return {"success": True, "data": sanitize_for_json(result)}
    except Exception as e:
        import traceback
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


@app.websocket("/api/v1/stream/{symbol}")
async def websocket_stream_endpoint(websocket: WebSocket, symbol: str, interval: str = "15m"):
    """
    Stream WebSocket en tiempo real para un símbolo dado.
    
    Fase 1: Envía historial reciente (500 velas) desde la API REST de Binance.
    Fase 2: Se suscribe al stream kline en tiempo real de Binance y retransmite cada tick.
    """
    await manager.connect(websocket)
    binance_ws = None
    
    try:
        # === FASE 1: Enviar historial (seed data) ===
        print(f"[{symbol}] Descargando historial desde Binance REST...")
        try:
            history = await fetch_binance_history(symbol, interval=interval, limit=500)
            await websocket.send_json({
                "type": "history",
                "data": history
            })
            print(f"[{symbol}] Historial enviado: {len(history)} velas.")
        except WebSocketDisconnect:
            raise
        except Exception as e:
            print(f"[{symbol}] No se pudo descargar historial de Binance: {e}. Usando datos locales.")
            # Fallback a Parquet local si Binance no está disponible
            file_path = Path(__file__).parent.parent.parent / "data" / f"{symbol.lower()}_{interval}.parquet"
            if file_path.exists():
                data = pd.read_parquet(file_path)
                hist_batch = []
                for _, row in data.iterrows():
                    hist_batch.append({
                        "type": "candle",
                        "data": {
                            "timestamp": row['timestamp'].timestamp(),
                            "open": float(row['open']),
                            "high": float(row['high']),
                            "low": float(row['low']),
                            "close": float(row['close']),
                            "volume": float(row['volume']),
                            "bullish_div": bool(row.get('bullish_div', False)),
                            "bearish_div": bool(row.get('bearish_div', False)),
                        }
                    })
                await websocket.send_json({"type": "history", "data": hist_batch})
        
        # === FASE 1b: Obtener Niveles Macro (MTF) ===
        macro_levels = None
        if interval not in ['1d', '1w']:
            print(f"[{symbol}] Descargando niveles MTF (1h, 4h)...")
            try:
                h1_data_raw = await fetch_binance_history(symbol, interval="1h", limit=200)
                h4_data_raw = await fetch_binance_history(symbol, interval="4h", limit=200)
                
                def _get_levels(raw_history, tf_name):
                    df = pd.DataFrame([item['data'] for item in raw_history])
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
                    df = identify_support_resistance(df, interval=tf_name)
                    return get_key_levels(df)

                l1h = _get_levels(h1_data_raw, "1h")
                l4h = _get_levels(h4_data_raw, "4h")
                
                from engine.indicators.structure import consolidate_mtf_levels
                macro_levels = consolidate_mtf_levels(l1h, l4h, timeframe_weight=3)
                print(f"[{symbol}] Niveles macro consolidados con éxito.")
            except Exception as e:
                print(f"[{symbol}] Error obteniendo niveles MTF: {e}")

        # === FASE 1c: Actualizar Ghost Data (Datos Fantasma - Nivel 1) ===
        ghost_state = None
        try:
            ghost_state = await refresh_ghost_data(symbol)
            ghost_payload = {
                "type": "ghost_update",
                "data": {
                    "fear_greed_value": ghost_state.fear_greed_value,
                    "fear_greed_label": ghost_state.fear_greed_label,
                    "btc_dominance":    ghost_state.btc_dominance,
                    "funding_rate":      ghost_state.funding_rate,
                    "macro_bias":        ghost_state.macro_bias,
                    "block_longs":       ghost_state.block_longs,
                    "block_shorts":      ghost_state.block_shorts,
                    "reason":            ghost_state.reason,
                }
            }
            await websocket.send_json(ghost_payload)
            print(f"[{symbol}] Ghost Data enviado: Bias={ghost_state.macro_bias}, F&G={ghost_state.fear_greed_value}")
        except WebSocketDisconnect:
            raise
        except Exception as e:
            print(f"[{symbol}] Ghost Data no disponible: {e}. Continuando sin filtro macro.")
            ghost_state = get_ghost_state()  # Usar caché incluso si está stale

        # === FASE 2: Stream en tiempo real desde Binance WebSocket ===
        import websockets as ws_client
        from engine.indicators.structure import identify_order_blocks, extract_smc_coordinates

        # Referencia a sesión actual para el Advisor (se llenará tras el bootstrap)
        initial_session = {'data': {'current_session': 'UNKNOWN'}}

        # Generar SMC Inicial con el historial que acabamos de cargar
        if history and len(history) > 0:
            print(f"[{symbol}] Calculando SMC y ML Inicial...")
            df_init = pd.DataFrame([item['data'] for item in history])
            df_init['timestamp'] = pd.to_datetime(df_init['timestamp'], unit='s')

            # ⚡ SESIONES PRIMERO: bootstrap y envío inmediato antes del SMC (que es lento)
            try:
                sm = get_session_manager(symbol)
                sm.bootstrap([item['data'] for item in history])
                initial_session = sm.get_current_state()
                await websocket.send_json(initial_session)
                print(f"[{symbol}] Session Update Inicial enviada: {initial_session['data']['current_session']} | {initial_session['data']['local_time']}")
            except WebSocketDisconnect:
                raise
            except Exception as e:
                print(f"[{symbol}] Error enviando session update inicial: {e}")

            # 🧠 DRIFT MONITOR: Establecer distribución de referencia con el historial
            try:
                fe = FeatureEngineer()
                df_features = fe.generate_features(df_init.copy())
                drift_monitor.set_reference(df_features)
            except Exception as e:
                print(f"[DRIFT] ⚠️  No se pudo establecer referencia: {e}")

            try:
                df_init_analyzed = identify_order_blocks(df_init)
                initial_smc = extract_smc_coordinates(df_init_analyzed)
                await websocket.send_json({
                    "type": "smc_data",
                    "data": initial_smc
                })
                print(f"[{symbol}] SMC Data Inicial enviada con éxito.")
                
                # Ejecutar el ruteo táctico con los datos iniciales y MTF
                # Pasar contexto al ConfluenceManager (sesiones + ML inicial aún vacío)
                engine_router.set_context(
                    session_data=initial_session.get('data', {}),
                )
                tactical_result = engine_router.process_market_data(
                    df_init.copy(), 
                    asset=symbol.upper(),
                    interval=interval,
                    macro_levels=macro_levels
                )
                await websocket.send_json({
                    "type": "tactical_update",
                    "data": tactical_result
                })
                print(f"[{symbol}] Decisión Táctica Inicial (MTF) enviada con éxito.")


                # 🤖 ANALISTA AUTÓNOMO (Llamada Inicial Tras Cargar Histórico)
                async def _emit_advisor_initial(ws, tactical, sess_name, ml_pred):
                    try:
                        advice_text = await generate_tactical_advice(
                            tactical_data=tactical,
                            current_session=sess_name,
                            ml_projection=ml_pred
                        )
                        await ws.send_json({"type": "advisor_update", "data": advice_text})
                        print(f"[{symbol}] Asesor Autónomo (LLM) informe inicial emitido.")
                    except asyncio.CancelledError:
                        pass
                    except Exception as e:
                        print(f"[{symbol}] Error ejecutando Asesor Autónomo inicial: {e}")
                
                asyncio.create_task(_emit_advisor_initial(
                    websocket, 
                    tactical_result,
                    initial_session['data'].get('current_session', 'UNKNOWN'),
                    None
                ))

            except WebSocketDisconnect:
                raise
            except Exception as e:
                print(f"[{symbol}] Error procesando SMC Inicial: {e}")

        # Conexión Multiplexada: Klines (Velas) + Order Book (Depth)
        kline_stream = f"{symbol.lower()}@kline_{interval}"
        depth_stream = f"{symbol.lower()}@depth20@100ms"
        binance_url = f"wss://stream.binance.com:9443/stream?streams={kline_stream}/{depth_stream}"
        
        print(f"[{symbol}] Conectando al stream multiplexado en tiempo real: {binance_url}")
        
        # Buffer en memoria para los recálculos en vivo
        # ✅ FIX: Usar deque(maxlen=500) para mayor precisión matemática en MACD/EMA/RSI
        live_candles_buffer: deque = deque(history[-500:], maxlen=500) if 'history' in locals() and history else deque(maxlen=500)
        
        # Estado de Liquidez en Tiempo Real
        # Nota: websocket_session_cache eliminado — SessionManager mantiene el estado internamente
        current_liquidity = {"bids": [], "asks": []}
        
        # Última predicción ML cacheada para no sobrecargar CPU en cada micro-tick
        last_ml_prediction = {"direction": "CALIBRANDO", "probability": 50, "status": "warmup"}
        
        # Control de Throttling para el Fast Path
        last_pulse_time = 0
        
        # Filtros Profesionales ML (Histéresis + EMA)
        ema_ml_prob = 50.0
        ml_smoothing_alpha = 0.2
        current_ml_direction = "ANALIZANDO"
        
        # Contador de cierres de vela — variable local (no atributo dinámico del WebSocket)
        candle_close_count = 0
        
        async with ws_client.connect(binance_url) as binance_ws:
            print(f"[{symbol}] Stream Multiplexado en tiempo real ACTIVO.")
            while True:
                try:
                    raw_message = await asyncio.wait_for(binance_ws.recv(), timeout=30.0)
                    multiplex_data = json.loads(raw_message)
                    
                    stream_type = multiplex_data.get('stream')
                    data = multiplex_data.get('data', {})
                    
                    # --- Procesar Stream de Liquidez (Order Book Depth) ---
                    if stream_type == depth_stream:
                        current_liquidity = detect_liquidity_clusters(
                            bids=data.get('bids', []),
                            asks=data.get('asks', []),
                            top_n=3
                        )
                        continue # Seguimos esperando Klines para inyectarlo en el Pulse
                        
                    # --- Procesar Stream de Velas (Klines) ---
                    if stream_type != kline_stream:
                        continue
                        
                    kline = data.get('k')
                    if not kline:
                        continue
                    
                    payload = {
                        "type": "candle",
                        "data": {
                            "timestamp": kline['t'] / 1000,
                            "open": float(kline['o']),
                            "high": float(kline['h']),
                            "low": float(kline['l']),
                            "close": float(kline['c']),
                            "volume": float(kline['v']),
                        }
                    }
                    await websocket.send_json(payload)
                    
                    # 🕒 SESIONES: Actualizar SessionManager en tiempo real (SMC Sweeps)
                    sm = get_session_manager(symbol)
                    sm.update(payload['data'])
                    session_payload = sm.get_current_state()
                    await websocket.send_json(session_payload)
                    
                    # === ROUTER SMC (Vía Cómputo Lenta, pero en Tiempo Real) ===
                    is_candle_closed = kline.get('x', False)
                    
                    # --- FAST PATH: Neural Pulse (Live Tick con Throttling) ---
                    current_time = time.time()
                    if current_time - last_pulse_time >= 1.0: # Max 1 actualización por segundo
                        last_pulse_time = current_time
                        
                        # ✨ RENOVACIÓN DINÁMICA DE GHOST DATA ✨
                        if not is_cache_fresh():
                            async def update_and_send_ghost():
                                try:
                                    fresh_ghost = await refresh_ghost_data(symbol)
                                    ghost_payload = {
                                        "type": "ghost_update",
                                        "data": {
                                            "fear_greed_value": fresh_ghost.fear_greed_value,
                                            "fear_greed_label": fresh_ghost.fear_greed_label,
                                            "btc_dominance":    fresh_ghost.btc_dominance,
                                            "funding_rate":      fresh_ghost.funding_rate,
                                            "macro_bias":        fresh_ghost.macro_bias,
                                            "block_longs":       fresh_ghost.block_longs,
                                            "block_shorts":      fresh_ghost.block_shorts,
                                            "reason":            fresh_ghost.reason,
                                        }
                                    }
                                    await websocket.send_json(ghost_payload)
                                    print(f"[{symbol}] [DINAMICO] Ghost Data enviado: Bias={fresh_ghost.macro_bias}, F&G={fresh_ghost.fear_greed_value}")
                                except Exception as e:
                                    print(f"[GHOST] Error en auto-refresco: {e}")
                            
                            asyncio.create_task(update_and_send_ghost())

                        # Para la inyección ML necesitamos un DataFrame actualizado
                        # Tomamos el buffer histórico y le sumamos el tick actual efímero
                        current_df_data = [item['data'] for item in live_candles_buffer] + [payload['data']]
                        if len(current_df_data) > 50: # Tenemos historia suficiente
                            df_live_tick = pd.DataFrame(current_df_data)
                            df_live_tick['timestamp'] = pd.to_datetime(df_live_tick['timestamp'], unit='s')
                            
                            # Realizamos la inferencia XGBoost
                            # (Es lo suficientemente rápido para correr 1 vez por segundo)
                            raw_prediction = ml_engine.predict_live(df_live_tick)
                            
                            # ✨ FILTRO PROFESIONAL: Suavizado EMA + Histéresis ✨
                            if raw_prediction.get("status") == "active":
                                raw_prob = raw_prediction.get("probability", 50)
                                raw_dir = raw_prediction.get("direction", "ANALIZANDO")
                                
                                # Convertir a probabilidad absoluta alcista (0-100)
                                prob_bullish_raw = raw_prob if raw_dir == "ALCISTA" else (100 - raw_prob)
                                
                                # 1. Aplicar Suavizado Exponencial (EMA)
                                ema_ml_prob = (prob_bullish_raw * ml_smoothing_alpha) + (ema_ml_prob * (1 - ml_smoothing_alpha))
                                
                                # 2. Aplicar Histéresis (Inercia de Estado)
                                if ema_ml_prob >= 55.0:
                                    current_ml_direction = "ALCISTA"
                                elif ema_ml_prob <= 45.0:
                                    current_ml_direction = "BAJISTA"
                                elif current_ml_direction == "ANALIZANDO":
                                    current_ml_direction = "NEUTRAL"
                                    
                                # Reconstruir la predicción filtrada
                                filtered_confidence = ema_ml_prob if current_ml_direction == "ALCISTA" else (100 - ema_ml_prob)
                                
                                last_ml_prediction = {
                                    "direction": current_ml_direction,
                                    "probability": int(filtered_confidence),
                                    "status": raw_prediction["status"],
                                    "reason": raw_prediction["reason"]
                                }
                            else:
                                last_ml_prediction = raw_prediction
                            
                            # ✨ NUEVO: HFT Confluence Matrix 
                            # Ejecutamos el router maestro en el Fast Path para hidratar la UI en tiempo real
                            try:
                                live_tactical = engine_router.process_market_data(
                                    df_live_tick, 
                                    asset=symbol.upper(), 
                                    interval=interval,
                                    macro_levels=macro_levels
                                )
                                await websocket.send_json({
                                    "type": "tactical_update",
                                    "data": live_tactical
                                })
                            except WebSocketDisconnect:
                                raise
                            except Exception as e:
                                print(f"[{symbol}] Error hidratando Confluence Matrix en vivo: {e}")
                            
                        # Extraer un log neural de sistema dinámico para la "cinta"
                        pulse_payload = {
                            "type": "neural_pulse",
                            "data": {
                                "ml_projection": last_ml_prediction,
                                "liquidity_heatmap": current_liquidity,
                                "log": {
                                    "type": "SENSOR",
                                    "message": f"[Fast Path] Analizando volatilidad de tick. Precio: ${float(kline['c']):.2f}"
                                }
                            }
                        }
                        await websocket.send_json(pulse_payload)
                        
                    # --- SLOW PATH: Procesamiento Estructural (Cierre de Vela) ---
                    # Si recibimos el tick de cierre final de la vela, ejecutamos análisis profundo
                    if is_candle_closed:
                        # Agregar nueva vela al buffer — deque(maxlen=250) descarta automáticamente la más vieja
                        live_candles_buffer.append(payload)
                        
                        # 2. Convertir buffer a DataFrame optimizado
                        df_data = [item['data'] for item in live_candles_buffer]
                        df_live = pd.DataFrame(df_data)
                        df_live['timestamp'] = pd.to_datetime(df_live['timestamp'], unit='s')

                        # 🧠 DRIFT MONITOR: Ejecutar cada 100 cierres de vela (≈ 25h en 15m)
                        candle_close_count += 1
                        if candle_close_count % 100 == 0:
                            try:
                                fe_live = FeatureEngineer()
                                df_live_features = fe_live.generate_features(df_live.copy())
                                drift_report = drift_monitor.check(df_live_features)
                                if drift_report and drift_report.alert_triggered:
                                    await websocket.send_json({
                                        "type": "drift_alert",
                                        "data": drift_report.to_dict()
                                    })
                                    # Notificar también por Telegram si está configurado
                                    from engine.notifications.telegram import send_drift_alert_async
                                    asyncio.create_task(send_drift_alert_async(drift_report.to_dict()))
                            except Exception as e:
                                print(f"[DRIFT] Error en check: {e}")

                        
                        # 3. Procesamiento Paralelo Matemático (SMC)
                        # Identificamos imbalances y estructuras (OBs)
                        df_analyzed = identify_order_blocks(df_live)
                        
                        # Extraemos las coordenadas vectorizadas
                        smc_coords = extract_smc_coordinates(df_analyzed)
                        
                        # 4. Enviar payload especial al Frontend
                        smc_payload = {
                            "type": "smc_data",
                            "data": smc_coords
                        }
                        await websocket.send_json(smc_payload)
                        print(f"[{symbol}] SMC Data emitida: OBs actualizados.")
                        
                        # 5. Procesamiento Matemático Final del Cerebro
                        try:
                            # Re-evaluamos con la vela oficialmente cerrada
                            # Actualizar contexto del ConfluenceManager con datos frescos
                            engine_router.set_context(
                                ml_projection=last_ml_prediction,
                                session_data=session_payload.get('data', {}) if 'session_payload' in locals() else {},
                            )
                            final_tactical = engine_router.process_market_data(
                                df_live, 
                                asset=symbol.upper(), 
                                interval=interval,
                                macro_levels=macro_levels
                            )
                            await websocket.send_json({
                                "type": "tactical_update",
                                "data": final_tactical
                            })
                            print(f"[{symbol}] Decisión Táctica Estructural de Cierre emitida.")


                            # 🔮 GHOST DATA: Filtrar señales por contexto macro (Nivel 1)
                            raw_signals = final_tactical.get('signals', [])
                            current_ghost = get_ghost_state()
                            macro_filtered_signals = filter_signals_by_macro(raw_signals, current_ghost)

                            if len(raw_signals) > len(macro_filtered_signals):
                                blocked = len(raw_signals) - len(macro_filtered_signals)
                                print(f"[GHOST] 🚫 {blocked} señal(es) bloqueada(s) por filtro macro: {current_ghost.macro_bias}")

                            # 💬 TELEGRAM: Notificar señales aprobadas por macro + anti-spam
                            for sig in macro_filtered_signals:
                                ok_to_send, block_reason = signal_filter.should_send(symbol, sig)
                                if ok_to_send:
                                    asyncio.create_task(send_signal_async(
                                        signal=sig,
                                        asset=symbol.upper(),
                                        regime=final_tactical.get('market_regime', 'UNKNOWN'),
                                        strategy=final_tactical.get('active_strategy', 'N/A')
                                    ))
                                else:
                                    print(f"[TELEGRAM] 🔕 Señal bloqueada por anti-spam: {block_reason}")
                        except WebSocketDisconnect:
                            raise
                        except Exception as e:
                            print(f"[{symbol}] Error emitiendo decisión táctica: {e}")

                        # 6. Sesiones de Mercado (Se emite en cada cierre de vela — is_closed=True para guardar en disco)
                        try:
                            sm = get_session_manager(symbol)
                            session_payload = sm.update(payload['data'], is_closed=True)
                            await websocket.send_json(session_payload)
                            print(f"[{symbol}] Session Update emitido: {session_payload['data']['current_session']} | {session_payload['data']['local_time']}")
                        except WebSocketDisconnect:
                            raise
                        except Exception as e:
                            print(f"[{symbol}] Error emitiendo session update: {e}")
                            session_payload = {'data': {'current_session': 'UNKNOWN'}}
                            
                        # 7. 🧠 ANALISTA AUTÓNOMO (LLM - Gemini)
                        # Se ejecuta al final de la cascada de la vela para tener todo el contexto.
                        # Envuelto en un task asíncrono para NO bloquear el event loop.
                        async def _emit_advisor(ws, tactical, sess, ml_pred):
                            try:
                                advice_text = await generate_tactical_advice(
                                    tactical_data=tactical,
                                    current_session=sess['data'].get('current_session', 'UNKNOWN'),
                                    ml_projection=ml_pred
                                )
                                await ws.send_json({"type": "advisor_update", "data": advice_text})
                                print(f"[{symbol}] Asesor Autónomo (LLM) informe emitido.")
                            except WebSocketDisconnect:
                                pass
                            except Exception as e:
                                print(f"[{symbol}] Error ejecutando Asesor Autónomo: {e}")
                        asyncio.create_task(_emit_advisor(
                            websocket, final_tactical,
                            session_payload if 'session_payload' in locals() else {'data': {}},
                            last_ml_prediction
                        ))
                    
                except asyncio.TimeoutError:
                    # Keepalive: si en 30s no llega nada, verificamos si el cliente sigue vivo
                    await websocket.send_json({"type": "ping"})
                    
    except WebSocketDisconnect:
        print(f"[{symbol}] Cliente desconectado.")
    except Exception as e:
        import traceback
        print(f"[{symbol}] Error en stream: {e}")
        traceback.print_exc()
    finally:
        manager.disconnect(websocket)
        print(f"[{symbol}] Limpieza completada.")


if __name__ == "__main__":
    import uvicorn
    print("[SLINGSHOT ENGINE] Iniciando en http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
