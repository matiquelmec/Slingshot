import asyncio
import websockets
import json
import time

async def latency_test():
    uri = "ws://localhost:8000/ws?client_id=titanium_test&asset=ETHUSDT&interval=15m"
    print(f"🔌 Conectando a {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Conectado. Midiendo latencias...")
            last_time = time.time()
            count = 0
            
            while count < 8:
                message = await websocket.recv()
                data = json.loads(message)
                msg_type = data.get("type")
                
                # Omitir historial
                if msg_type in ["history", "ghost_update", "radar_update", "session_update", "liquidation_update", "signal_auditor_update"]:
                    continue
                
                now = time.time()
                delta = (now - last_time) * 1000
                print(f"📥 [{msg_type}] Latencia desde último tick: {delta:.2f}ms")
                last_time = now
                count += 1
                
    except Exception as e:
        print(f"❌ Error: {e}")

asyncio.run(latency_test())
