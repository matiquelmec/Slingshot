import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import httpx
import pandas as pd
import json
from datetime import datetime

# Importar el Enrutador Maestro del Engine
from engine.main_router import SlingshotRouter
from engine.api.config import settings
from engine.api.ws_manager import manager

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
        result = engine_router.process_market_data(data, asset=symbol.upper())
        
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
        
        # === FASE 2: Stream en tiempo real desde Binance WebSocket ===
        import websockets as ws_client
        from engine.indicators.structure import identify_order_blocks, extract_smc_coordinates
        
        # Generar SMC Inicial con el historial que acabamos de cargar
        if history and len(history) > 0:
            print(f"[{symbol}] Calculando SMC Engine Inicial...")
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
            except Exception as e:
                print(f"[{symbol}] Error procesando SMC Inicial: {e}")

        stream_name = f"{symbol.lower()}@kline_{interval}"
        binance_url = f"wss://stream.binance.com:9443/ws/{stream_name}"
        
        print(f"[{symbol}] Conectando al stream en tiempo real: {stream_name}")
        
        # Buffer en memoria para los recálculos en vivo
        live_candles_buffer = history[-200:] if 'history' in locals() else []
        
        async with ws_client.connect(binance_url) as binance_ws:
            print(f"[{symbol}] Stream en tiempo real ACTIVO.")
            while True:
                try:
                    raw_message = await asyncio.wait_for(binance_ws.recv(), timeout=30.0)
                    data = json.loads(raw_message)
                    
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
                    
                    # Si recibimos el tick de cierre final de la vela, ejecutamos análisis profundo
                    if is_candle_closed:
                        # 1. Agregar nueva vela al buffer
                        date_obj = datetime.fromtimestamp(kline['t'] / 1000)
                        live_candles_buffer.append(payload)
                        
                        # Mantener el buffer manejable (200 velas para SMC es suficiente)
                        if len(live_candles_buffer) > 200:
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
