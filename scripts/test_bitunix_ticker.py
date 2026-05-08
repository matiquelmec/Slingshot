import asyncio
import httpx
import json
import time

async def test_bitunix_ticker():
    print("Probando Bitunix Ticker...")
    url = "https://fapi.bitunix.com/api/v1/futures/market/ticker"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, params={"symbol": "BTCUSDT"}, timeout=5)
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                print(f"Data: {json.dumps(resp.json(), indent=2)}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_bitunix_ticker())
