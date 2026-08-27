import asyncio
import sys
import time
sys.path.insert(0, ".")

from engine.workers.market_scanner import MarketScanner
from engine.core.store import store

async def main():
    s = MarketScanner()
    t0 = time.time()
    await s._scan_timeframe("15m", "scalp")
    t1 = time.time()
    
    scalp = store.get_scanner_opportunities("scalp")
    print(f"=== 15M SCALP SCAN COMPLETED IN {t1-t0:.2f} SECONDS ===")
    print(f"TOTAL 15M OPPORTUNITIES: {len(scalp)}")
    for o in scalp[:10]:
        print(f"  - {o['asset']:<10} | {o['direction']:<5} | Score: {o.get('confluence_score'):>3}% | Entry: ${o.get('price'):<8} | TP1: ${o.get('tp1'):<8} | TP3: ${o.get('tp3')}")

if __name__ == "__main__":
    asyncio.run(main())
