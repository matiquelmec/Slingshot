# scratch/audit_data_ingestion.py
import asyncio
import json
import time
import websockets
from collections import defaultdict

# Watchlist de Slingshot
FUTURES_ASSETS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "XAGUSDT"]
SPOT_ASSETS = ["PAXGUSDT"]

# Diccionarios de estadísticas
message_stats = defaultdict(lambda: {"klines": 0, "depth": 0, "last_msg_time": 0.0})

# URL de los WebSockets
FUTURES_WS_URL = "wss://fstream.binance.com/stream?streams=" + "/".join(
    [f"{a.lower()}@kline_1m/{a.lower()}@depth20@500ms" for a in FUTURES_ASSETS]
)
SPOT_WS_URL = "wss://stream.binance.com:9443/stream?streams=" + "/".join(
    [f"{a.lower()}@kline_1m/{a.lower()}@depth20" for a in SPOT_ASSETS]
)

async def monitor_stream(url: str, label: str):
    """Escucha el stream de WebSocket de Binance y tabula estadísticas."""
    print(f"[AUDIT] Conectando a WebSocket {label}...")
    try:
        async with websockets.connect(url, ping_interval=30) as ws:
            print(f"[AUDIT] Conexión establecida con {label} con éxito.")
            while True:
                raw_msg = await ws.recv()
                msg = json.loads(raw_msg)
                
                stream_name = msg.get("stream", "").lower()
                data = msg.get("data", {})
                
                # Obtener el par/símbolo del mensaje
                symbol = data.get("s", "").upper()
                event_type = data.get("e", "")
                
                if not symbol:
                    continue
                    
                now = time.time()
                message_stats[symbol]["last_msg_time"] = now
                
                if "kline" in stream_name or event_type == "kline":
                    message_stats[symbol]["klines"] += 1
                elif "depth" in stream_name or "depth" in event_type:
                    message_stats[symbol]["depth"] += 1
                    
    except asyncio.CancelledError:
        print(f"[AUDIT] Deteniendo escucha en {label}.")
    except Exception as e:
        print(f"[ERROR] Fallo en stream {label}: {e}")

async def print_stats_loop(duration_seconds: int = 600):
    """Imprime el resumen de auditoría en consola cada 10 segundos."""
    start_time = time.time()
    elapsed = 0
    
    while elapsed < duration_seconds:
        await asyncio.sleep(10)
        elapsed = int(time.time() - start_time)
        
        print("\n" + "="*70)
        print(f" REPORTE DE AUDITORÍA DE TELEMETRÍA (Transcurrido: {elapsed}s / {duration_seconds}s)")
        print("="*70)
        print(f"{'Activo':<12} | {'Mensajes Kline (1m)':<22} | {'Mensajes Depth':<18} | {'Última Señal (hace)'}")
        print("-"*70)
        
        # Combinamos toda la watchlist
        for asset in sorted(FUTURES_ASSETS + SPOT_ASSETS):
            stats = message_stats[asset]
            last_seen = "Nunca"
            if stats["last_msg_time"] > 0:
                last_seen = f"{time.time() - stats['last_msg_time']:.1f}s"
                
            print(f"{asset:<12} | {stats['klines']:<22} | {stats['depth']:<18} | {last_seen}")
        print("="*70)

async def main():
    print("="*70)
    print(" INICIANDO AUDITORÍA EN VIVO DE ENTRADA DE DATOS (BINANCE API) ")
    print("="*70)
    print(f"Monitoreando Futuros: {FUTURES_ASSETS}")
    print(f"Monitoreando Spot   : {SPOT_ASSETS}")
    print("Ejecutando monitoreo durante 10 minutos (600 segundos)...")
    print("="*70)
    
    # Crear tareas para los dos streams y el loop de reportes
    t_futures = asyncio.create_task(monitor_stream(FUTURES_WS_URL, "Binance Futures"))
    t_spot = asyncio.create_task(monitor_stream(SPOT_WS_URL, "Binance Spot"))
    t_reporter = asyncio.create_task(print_stats_loop(600))
    
    try:
        # Esperar a que el reportero termine (los 10 minutos)
        await t_reporter
    except KeyboardInterrupt:
        print("\n[AUDIT] Monitoreo interrumpido por el usuario.")
    finally:
        # Cancelar streams de fondo de forma limpia
        t_futures.cancel()
        t_spot.cancel()
        await asyncio.gather(t_futures, t_spot, return_exceptions=True)
        print("\n[AUDIT] Auditoría finalizada.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
