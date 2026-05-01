import asyncio
import httpx

async def test_binance():
    url = "https://fapi.binance.com/fapi/v1/openInterest"
    params = {"symbol": "BTCUSDT"}
    print(f"Testing {url}...")
    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            r = await client.get(url, params=params)
            print(f"Status: {r.status_code}")
            print(f"Response: {r.text[:200]}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_binance())
