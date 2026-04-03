import asyncio
import base64
import json
import time
import uuid
import sys
import websockets

async def run_latency_stress_test():
    uri = "ws://localhost:8000/ws?client_id=stress-1234&asset=ETHUSDT&interval=15m"
    print(f"🔌 Conectando a {uri} para prueba de 5 minutos...")
    
    start_time = time.time()
    latencies = []
    
    try:
        async with websockets.connect(uri, ping_interval=20, ping_timeout=20, open_timeout=60) as websocket:
            print("✅ Conectado. Midiendo Latency (Drift) durante el streaming de ETHUSDT...")
            last_pulse = time.time()
            
            while time.time() - start_time < 30: # 30 segundos
                try:
                    # Usar un timeout pequeño para imprimir el progreso
                    message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(message)
                    msg_type = data.get("type", "")
                    
                    if msg_type in ["neural_pulse", "tactical_update"]:
                        now = time.time()
                        drift = (now - last_pulse) * 1000
                        
                        # Filtrar latencias inválidas de primer arranque (~10k+ ms)
                        if len(latencies) > 0 or drift < 5000:
                            latencies.append(drift)
                        
                        last_pulse = now
                        sys.stdout.write(f"\r📥 Tick {msg_type} recibido. Latency Drift: {drift:.2f}ms  ")
                        sys.stdout.flush()
                        
                except asyncio.TimeoutError:
                    continue
                    
    except Exception as e:
        print(f"\n❌ Se colapso WS: {e}")
        
    print("\n\n📊 REPORTE DE LATENCIA:")
    if latencies:
        avg = sum(latencies) / len(latencies)
        p99 = sorted(latencies)[int(len(latencies)*0.99)] if len(latencies) > 10 else max(latencies)
        print(f" - Muestras: {len(latencies)}")
        print(f" - Promedio (Drift): {avg:.2f}ms")
        print(f" - Pico máximo (P99): {p99:.2f}ms")
    else:
        print("No se registraron ticks.")

asyncio.run(run_latency_stress_test())
