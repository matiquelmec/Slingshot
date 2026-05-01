
import httpx
import asyncio
import sys

async def debug_binance():
    symbol = "BTCUSDT"
    mirrors = [
        "https://fapi.binance.com",
        "https://fapi1.binance.com",
        "https://fapi2.binance.com",
        "https://fapi3.binance.com"
    ]
    
    print(f"--- Debugging Binance Connectivity for {symbol} ---")
    
    for url in mirrors:
        full_url = f"{url}/fapi/v1/openInterest?symbol={symbol}"
        print(f"\nTrying {full_url}...")
        try:
            async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
                r = await client.get(full_url)
                print(f"Status: {r.status_code}")
                if r.status_code == 200:
                    print(f"Success! Data: {r.json()}")
                    break
                else:
                    print(f"Failed with status {r.status_code}: {r.text}")
        except Exception as e:
            print(f"Exception Type: {type(e).__name__}")
            print(f"Exception Detail: {str(e)}")

if __name__ == "__main__":
    # Disable warnings for verify=False
    import urllib3
    urllib3.disable_warnings()
    asyncio.run(debug_binance())
