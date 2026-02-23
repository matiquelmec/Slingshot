import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import httpx
import pandas as pd
import json
from datetime import datetime, timezone
import pytz

# Importar el Enrutador Maestro del Engine
from engine.main_router import SlingshotRouter
from engine.api.config import settings
from engine.api.ws_manager import manager


def build_session_update(df_buffer: list) -> dict:
    """
    Calcula el estado actual de las sesiones de mercado basado en UTC del servidor.
    Extrae H/L de cada sesión y estados de sweep del buffer de velas.
    """
    now_utc = datetime.now(timezone.utc)
    hour_utc = now_utc.hour
    chile_tz = pytz.timezone('America/Santiago')
    now_chile = now_utc.astimezone(chile_tz)
    utc_str = now_utc.strftime('%H:%M UTC')
    local_str = now_chile.strftime('%H:%M Chile')

    # Determinar sesión activa
    if 0 <= hour_utc < 6:
        session_name = 'ASIA'
        is_killzone = False
    elif 7 <= hour_utc < 10:
        session_name = 'LONDON_KILLZONE'
        is_killzone = True
    elif 10 <= hour_utc < 13:
        session_name = 'LONDON'
        is_killzone = False
    elif 13 <= hour_utc < 16:
        session_name = 'NY_KILLZONE'
        is_killzone = True
    elif 16 <= hour_utc < 20:
        session_name = 'NEW_YORK'
        is_killzone = False
    else:
        session_name = 'OFF_HOURS'
        is_killzone = False

    # Extraer H/L por sesión del buffer si hay datos
    sessions_data = {
        'asia':   {'high': None, 'low': None, 'status': 'CLOSED', 'swept_high': False, 'swept_low': False},
        'london': {'high': None, 'low': None, 'status': 'PENDING', 'swept_high': False, 'swept_low': False},
        'ny':     {'high': None, 'low': None, 'status': 'PENDING', 'swept_high': False, 'swept_low': False},
    }
    pdh, pdl = None, None
    pdh_swept, pdl_swept = False, False

    if df_buffer and len(df_buffer) > 0:
        try:
            import pandas as pd
            from engine.indicators.sessions import map_sessions_liquidity
            df = pd.DataFrame([item['data'] for item in df_buffer[-250:]])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s', utc=True)
            df = map_sessions_liquidity(df)
            last = df.iloc[-1]

            # Sesión Asia
            if pd.notna(last.get('asian_high')):
                sessions_data['asia']['high'] = float(last['asian_high'])
                sessions_data['asia']['low'] = float(last['asian_low'])
                sessions_data['asia']['swept_high'] = bool(last.get('sweep_asian_high', False))
                sessions_data['asia']['swept_low'] = bool(last.get('sweep_asian_low', False))

            # Sesión Londres
            if pd.notna(last.get('london_high')):
                sessions_data['london']['high'] = float(last['london_high'])
                sessions_data['london']['low'] = float(last['london_low'])
                sessions_data['london']['swept_high'] = bool(last.get('sweep_london_high', False))
                sessions_data['london']['swept_low'] = bool(last.get('sweep_london_low', False))

            # Sesión NY
            if pd.notna(last.get('ny_high')):
                sessions_data['ny']['high'] = float(last['ny_high'])
                sessions_data['ny']['low'] = float(last['ny_low'])
                sessions_data['ny']['swept_high'] = bool(last.get('sweep_ny_high', False))
                sessions_data['ny']['swept_low'] = bool(last.get('sweep_ny_low', False))

            # PDH / PDL
            if pd.notna(last.get('previous_daily_high')):
                pdh = float(last['previous_daily_high'])
                pdl = float(last['previous_daily_low'])
                pdh_swept = bool(last.get('sweep_pdh', False))
                pdl_swept = bool(last.get('sweep_pdl', False))
        except Exception:
            pass

    # Marcar estados de sesión según la hora actual
    if hour_utc < 6:
        sessions_data['asia']['status'] = 'ACTIVE'
    elif hour_utc < 15:
        sessions_data['asia']['status'] = 'CLOSED'
        sessions_data['london']['status'] = 'ACTIVE' if hour_utc >= 7 else 'PENDING'
    else:
        sessions_data['asia']['status'] = 'CLOSED'
        sessions_data['london']['status'] = 'CLOSED'
        sessions_data['ny']['status'] = 'ACTIVE' if hour_utc >= 13 else 'PENDING'
    if hour_utc >= 20:
        sessions_data['ny']['status'] = 'CLOSED'

    return {
        'type': 'session_update',
        'data': {
            'current_session': session_name,
            'current_session_utc': utc_str,
            'local_time': local_str,
            'is_killzone': is_killzone,
            'sessions': sessions_data,
            'pdh': pdh,
            'pdl': pdl,
            'pdh_swept': pdh_swept,
            'pdl_swept': pdl_swept,
        }
    }

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Capa 4: Puente de Conectividad de Alta Velocidad para el Motor Cuantitativo",
    version=settings.VERSION,
)

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
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
    """
    try:
        file_path = Path(__file__).parent.parent.parent / "data" / f"{symbol.lower()}_{timeframe}.parquet"
        
        if not file_path.exists():
            return {"error": f"No hay datos locales para {symbol} en {timeframe}"}
            
        data = pd.read_parquet(file_path)
        result = engine_router.process_market_data(data, asset=symbol.upper(), interval=timeframe)
        
        return {"success": True, "data": result}
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
            for candle in history:
                await websocket.send_json(candle)
            print(f"[{symbol}] Historial enviado: {len(history)} velas.")
        except Exception as e:
            print(f"[{symbol}] No se pudo descargar historial de Binance: {e}. Usando datos locales.")
            # Fallback a Parquet local si Binance no está disponible
            file_path = Path(__file__).parent.parent.parent / "data" / f"{symbol.lower()}_{interval}.parquet"
            if file_path.exists():
                data = pd.read_parquet(file_path)
                for _, row in data.iterrows():
                    await websocket.send_json({
                        "type": "candle",
                        "data": {
                            "timestamp": row['timestamp'].timestamp(),
                            "open": float(row['open']),
                            "high": float(row['high']),
                            "low": float(row['low']),
                            "close": float(row['close']),
                            "volume": float(row['volume']),
                        }
                    })
                    await asyncio.sleep(0.01)  # No bloquear el event loop
        
        # === FASE 1b: Obtener Niveles Macro (MTF) ===
        macro_levels = None
        if interval not in ['1d', '1w']:
            print(f"[{symbol}] Descargando niveles MTF (1h, 4h)...")
            try:
                # Descargar 1h y 4h para confluencia
                h1_data_raw = await fetch_binance_history(symbol, interval="1h", limit=200)
                h4_data_raw = await fetch_binance_history(symbol, interval="4h", limit=200)
                
                def _get_levels(raw_history, tf_name):
                    df = pd.DataFrame([item['data'] for item in raw_history])
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
                    df = identify_support_resistance(df, interval=tf_name)
                    return get_key_levels(df)

                l1h = _get_levels(h1_data_raw, "1h")
                l4h = _get_levels(h4_data_raw, "4h")
                
                # Fusionar macro_levels (l4h tiene más peso que l1h)
                from engine.indicators.structure import consolidate_mtf_levels
                macro_levels = consolidate_mtf_levels(l1h, l4h, timeframe_weight=3)
                print(f"[{symbol}] Niveles macro consolidados con éxito.")
            except Exception as e:
                print(f"[{symbol}] Error obteniendo niveles MTF: {e}")

        # === FASE 2: Stream en tiempo real desde Binance WebSocket ===
        import websockets as ws_client
        from engine.indicators.structure import identify_order_blocks, extract_smc_coordinates
        
        # Generar SMC Inicial con el historial que acabamos de cargar
        if history and len(history) > 0:
            print(f"[{symbol}] Calculando SMC y ML Inicial...")
            df_init = pd.DataFrame([item['data'] for item in history])
            df_init['timestamp'] = pd.to_datetime(df_init['timestamp'], unit='s')
            try:
                df_init_analyzed = identify_order_blocks(df_init)
                initial_smc = extract_smc_coordinates(df_init_analyzed)
                await websocket.send_json({
                    "type": "smc_data",
                    "data": initial_smc
                })
                print(f"[{symbol}] SMC Data Inicial enviada con éxito.")
                
                # Ejecutar el ruteo táctico con los datos iniciales y MTF
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


                # Session update inicial: emitir inmediatamente con el historial cargado
                try:
                    initial_session = build_session_update(history)
                    await websocket.send_json(initial_session)
                    print(f"[{symbol}] Session Update Inicial enviada: {initial_session['data']['current_session']}")
                except Exception as e:
                    print(f"[{symbol}] Error enviando session update inicial: {e}")

            except Exception as e:
                print(f"[{symbol}] Error procesando SMC Inicial: {e}")

        # Conexión Multiplexada: Klines (Velas) + Order Book (Depth)
        kline_stream = f"{symbol.lower()}@kline_{interval}"
        depth_stream = f"{symbol.lower()}@depth20@100ms"
        binance_url = f"wss://stream.binance.com:9443/stream?streams={kline_stream}/{depth_stream}"
        
        print(f"[{symbol}] Conectando al stream multiplexado en tiempo real: {binance_url}")
        
        # Buffer en memoria para los recálculos en vivo
        live_candles_buffer = history[-250:] if 'history' in locals() else []
        
        # Estado de Liquidez en Tiempo Real
        current_liquidity = {"bids": [], "asks": []}
        from engine.indicators.liquidity import detect_liquidity_clusters
        from engine.ml.inference import ml_engine
        
        # Última predicción ML cacheada para no sobrecargar CPU en cada micro-tick
        last_ml_prediction = {"direction": "CALIBRANDO", "probability": 50, "status": "warmup"}
        
        # Control de Throttling para el Fast Path
        last_pulse_time = 0
        import time
        import random
        
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
                    
                    # === ROUTER SMC (Vía Cómputo Lenta, pero en Tiempo Real) ===
                    is_candle_closed = kline.get('x', False)
                    
                    # --- FAST PATH: Neural Pulse (Live Tick con Throttling) ---
                    current_time = time.time()
                    if current_time - last_pulse_time >= 1.0: # Max 1 actualización por segundo
                        last_pulse_time = current_time
                        
                        # Para la inyección ML necesitamos un DataFrame actualizado
                        # Tomamos el buffer histórico y le sumamos el tick actual efímero
                        current_df_data = [item['data'] for item in live_candles_buffer] + [payload['data']]
                        if len(current_df_data) > 50: # Tenemos historia suficiente
                            df_live_tick = pd.DataFrame(current_df_data)
                            df_live_tick['timestamp'] = pd.to_datetime(df_live_tick['timestamp'], unit='s')
                            
                            # Realizamos la inferencia XGBoost
                            # (Es lo suficientemente rápido para correr 1 vez por segundo)
                            last_ml_prediction = ml_engine.predict_live(df_live_tick)
                            
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
                        # 1. Agregar nueva vela al buffer
                        date_obj = datetime.fromtimestamp(kline['t'] / 1000)
                        live_candles_buffer.append(payload)
                        
                        # Mantener el buffer manejable (250 velas es suficiente para SMA200 y SMC)
                        if len(live_candles_buffer) > 250:
                            live_candles_buffer.pop(0)
                        
                        # 2. Convertir buffer a DataFrame optimizado
                        # Extraemos solo la parte 'data' para Pandas
                        df_data = [item['data'] for item in live_candles_buffer]
                        df_live = pd.DataFrame(df_data)
                        df_live['timestamp'] = pd.to_datetime(df_live['timestamp'], unit='s')
                        
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
                        
                        # 5. Procesamiento Matemático del Cerebro (Decisión Táctica)
                        try:
                            # Pasamos el DataFrame entero al motor para un análisis contextual
                            tactical_result = engine_router.process_market_data(
                                df_live, 
                                asset=symbol.upper(), 
                                interval=interval,
                                macro_levels=macro_levels
                            )
                            tactical_payload = {
                                "type": "tactical_update",
                                "data": tactical_result
                            }
                            await websocket.send_json(tactical_payload)
                            print(f"[{symbol}] Decisión Táctica Estructural emitida.")
                        except Exception as e:
                            print(f"[{symbol}] Error emitiendo decisión táctica: {e}")

                        # 6. Sesiones de Mercado (Se emite en cada cierre de vela)
                        try:
                            session_payload = build_session_update(live_candles_buffer)
                            await websocket.send_json(session_payload)
                            print(f"[{symbol}] Session Update emitido: {session_payload['data']['current_session']}")
                        except Exception as e:
                            print(f"[{symbol}] Error emitiendo session update: {e}")
                    
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
