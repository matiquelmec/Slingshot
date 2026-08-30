import asyncio
import sys
import json
sys.path.insert(0, ".")

from scripts.test_bitunix_connection import BitunixTester

async def main():
    tester = BitunixTester()
    res = await tester.request("GET", "/api/v1/futures/trade/get_pending_orders", params={"symbol": "XAGUSDT"})
    print("Pending Orders for XAGUSDT:")
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
