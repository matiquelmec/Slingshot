import asyncio
import sys
sys.path.insert(0, ".")

from engine.workers.market_scanner import MarketScanner
from engine.core.store import store

async def main():
    s = MarketScanner()
    await s._perform_scan()
    
    scalp = store.get_scanner_opportunities("scalp")
    swing = store.get_scanner_opportunities("swing")
    daily = store.get_scanner_opportunities("daily")
    
    print("=== SCANNER RESULTS ===")
    print(f"15M SCALP TOTAL: {len(scalp)}")
    for o in scalp[:10]:
        print(f"  - {o['asset']} ({o['direction']}) | Score: {o.get('confluence_score')}% | Entry: ${o.get('price')} | Type: {o.get('type')}")
        
    print(f"\n1H SWING TOTAL: {len(swing)}")
    for o in swing[:5]:
        print(f"  - {o['asset']} ({o['direction']}) | Score: {o.get('confluence_score')}%")
        
    print(f"\n1D DAILY TOTAL: {len(daily)}")
    for o in daily[:5]:
        print(f"  - {o['asset']} ({o['direction']}) | Score: {o.get('confluence_score')}%")

if __name__ == "__main__":
    asyncio.run(main())
