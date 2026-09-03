import asyncio
import sys
import json
sys.path.insert(0, ".")

from engine.execution.bitunix_executor import BitunixExecutor

async def main():
    executor = BitunixExecutor(dry_run=False)
    symbol = "XAGUSDT"
    position_id = "4755897071119796288"
    
    entry_price = 72.75
    sl_price = entry_price * 0.98 # 71.295
    tp_price = entry_price * 1.06 # 77.115
    
    print(f"Placing Position TP/SL on XAGUSDT Position ID {position_id}...")
    
    payload = {
        "symbol": symbol,
        "positionId": position_id,
        "slPrice": str(round(sl_price, 2)),
        "slStopType": "LAST_PRICE",
        "tpPrice": str(round(tp_price, 2)),
        "tpStopType": "LAST_PRICE"
    }
    
    res = await executor._request("POST", "/api/v1/futures/tpsl/position/place_order", json_body=payload)
    print("Position TP/SL Response:")
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
