
import httpx
import asyncio

async def test_symbols():
    symbols = ["BTCUSDT", "XAGUSDT", "PAXGUSDT"]
    base_url = "https://fapi.binance.com"
    
    async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
        for s in symbols:
            r = await client.get(f"{base_url}/fapi/v1/openInterest", params={"symbol": s})
            print(f"Symbol {s} | Status: {r.status_code} | Body: {r.text[:100]}")

if __name__ == "__main__":
    asyncio.run(test_symbols())
