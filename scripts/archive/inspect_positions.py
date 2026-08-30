import asyncio
import sys
import json
sys.path.insert(0, ".")

from scripts.test_bitunix_connection import BitunixTester

async def main():
    tester = BitunixTester()
    pos = await tester.request("GET", "/api/v1/futures/position/get_pending_positions")
    print(json.dumps(pos, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
