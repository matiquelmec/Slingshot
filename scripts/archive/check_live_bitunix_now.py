import asyncio
import sys
sys.path.insert(0, ".")

from engine.execution.bitunix_executor import BitunixExecutor

async def main():
    executor = BitunixExecutor()
    positions = await executor.get_pending_positions()
    print("=== POSICIONES REALES ACTIVAS EN BITUNIX ===")
    if not positions:
        print("No hay posiciones abiertas en Bitunix.")
    for p in positions:
        print(f"Símbolo: {p.get('symbol')}")
        print(f"  - Lado: {p.get('side')} (Position ID: {p.get('positionId')})")
        print(f"  - Cantidad: {p.get('qty')} / Hold: {p.get('holdVol')}")
        print(f"  - Precio Entrada: {p.get('entryPrice')}")
        print(f"  - Stop Loss Actual en Bitunix: {p.get('stopLoss')}")
        print(f"  - Take Profit Actual en Bitunix: {p.get('takeProfit')}")
        print(f"  - PnL no realizado: {p.get('unrealizedPnl')}")

    print("\n=== ÓRDENES TPSL PENDIENTES EN BITUNIX ===")
    for p in positions:
        sym = p.get('symbol')
        tpsl_res = await executor._request("GET", "/api/v1/futures/tpsl/get_pending_orders", params={"symbol": sym})
        print(f"TPSL para {sym}: {tpsl_res.get('data')}")

if __name__ == "__main__":
    asyncio.run(main())
