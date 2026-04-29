import asyncio
import httpx

async def check_symbols():
    url = "https://api.binance.com/api/v3/exchangeInfo"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        data = response.json()
        symbols = [s['symbol'] for s in data['symbols']]
        
        print("Searching for Oil/WTI symbols on Spot...")
        oil_symbols = [s for s in symbols if "OIL" in s or "WTI" in s]
        print(f"Found: {oil_symbols}")
        
        for s in ["XRPUSDT", "XAGUSDT", "PAXGUSDT"]:
            print(f"Spot {s}: {'VALID' if s in symbols else 'INVALID'}")

if __name__ == "__main__":
    asyncio.run(check_symbols())
