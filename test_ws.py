import asyncio
import websockets
import json

async def test_binance():
    url = "wss://stream.binance.com:9443/stream?streams=btcusdt@kline_1m"
    print(f"Connecting to {url}...")
    try:
        async with websockets.connect(url, ping_interval=30) as ws:
            print("Connected! Waiting for kline messages...")
            for _ in range(2):
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
                data = json.loads(msg)
                if 'data' in data and 'e' in data['data']:
                    print(f"Received event: {data['data']['e']}")
                else:
                    print(f"Received message: {str(msg)[:100]}...")
            print("Successfully received data.")
    except Exception as e:
        print(f"Error: {repr(e)}")

if __name__ == "__main__":
    asyncio.run(test_binance())
