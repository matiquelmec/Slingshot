import asyncio
import sys
sys.path.insert(0, ".")

from engine.execution.bitunix_executor import BitunixExecutor

async def main():
    executor = BitunixExecutor()
    orders = await executor.get_pending_orders()
    print("=== ÓRDENES LÍMITE PENDIENTES EN BITUNIX ===")
    for o in orders:
        print(f"Orden ID: {o.get('orderId')} | Symbol: {o.get('symbol')} | Side: {o.get('side')} | Price: ${o.get('price')} | Qty: {o.get('qty')} | Type: {o.get('orderType')}")

if __name__ == "__main__":
    asyncio.run(main())
