import asyncio
import httpx
import websockets
import json

BASE_URL = 'http://127.0.0.1:8000'
BASE_WS = 'ws://127.0.0.1:8000'
API_KEY = 'SLINGSHOT_INTERNAL_V6'

async def test_ws():
    print("1. Fetching token...")
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{BASE_URL}/api/v1/auth/token?api_key={API_KEY}")
            if r.status_code != 200:
                print("Failed to get token:", r.status_code)
                return
            token = r.json()["token"]
            print("Token retrieved successfully:", token)

        ws_url = f"{BASE_WS}/api/v1/stream/BTCUSDT?token={token}&interval=15m"
        print(f"\n2. Connecting to WebSocket: {ws_url}...")
        async with websockets.connect(ws_url) as ws:
            print("Connected! Waiting for 3 messages to verify stream integrity...")
            for i in range(3):
                msg = await ws.recv()
                data = json.loads(msg)
                print(f"\n[MSG #{i+1}] Type: {data.get('type')}")
                if data.get('type') == 'smc_data':
                    print("Dynamic SMC Order Blocks:")
                    print(json.dumps(data.get('data', {}).get('order_blocks'), indent=2))
                elif data.get('type') == 'radar_update':
                    print(f"Radar assets count: {len(data.get('data', []))}")
                elif data.get('type') == 'history':
                    print(f"Candles history count: {len(data.get('data', []))}")
                    
    except Exception as e:
        import traceback
        print("Error during test:")
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test_ws())
