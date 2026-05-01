
import asyncio
import httpx

async def test_apis():
    print("Testing Fear & Greed...")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get("https://api.alternative.me/fng/?limit=1&format=json")
            print(f"F&G Status: {r.status_code}")
            print(f"F&G Data: {r.text[:200]}")
    except Exception as e:
        print(f"F&G Error: {e}")

    print("\nTesting CoinGecko Global...")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get("https://api.coingecko.com/api/v3/global")
            print(f"CoinGecko Status: {r.status_code}")
            print(f"CoinGecko Data: {r.text[:200]}")
    except Exception as e:
        print(f"CoinGecko Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_apis())
