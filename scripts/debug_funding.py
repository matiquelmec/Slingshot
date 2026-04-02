import httpx
import asyncio

async def check():
    async with httpx.AsyncClient() as client:
        # Check BTC
        r_btc = await client.get("https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT")
        btc_data = r_btc.json()
        btc_fr = float(btc_data.get("lastFundingRate", 0)) * 100
        
        # Check PAXG
        r_pax = await client.get("https://fapi.binance.com/fapi/v1/premiumIndex?symbol=PAXGUSDT")
        pax_data = r_pax.json()
        pax_fr = float(pax_data.get("lastFundingRate", 0)) * 100
        
        print(f"BTC_FUNDING: {btc_fr:.5f}%")
        print(f"PAXG_FUNDING: {pax_fr:.5f}%")

if __name__ == "__main__":
    asyncio.run(check())
