import asyncio
import httpx
import json

async def test_bitunix_depth():
    print("Probando Bitunix Depth...")
    # Endpoints comunes en Bitunix
    urls = [
        "https://fapi.bitunix.com/api/v1/futures/market/depth",
        "https://fapi.bitunix.com/api/v1/futures/market/orderbook"
    ]
    
    async with httpx.AsyncClient() as client:
        for url in urls:
            try:
                print(f"Tratando {url}...")
                resp = await client.get(url, params={"symbol": "BTCUSDT"}, timeout=5)
                print(f"Status: {resp.status_code}")
                if resp.status_code == 200:
                    data = resp.json()
                    print(f"Data: {json.dumps(data, indent=2)[:500]}")
            except Exception as e:
                print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_bitunix_depth())
