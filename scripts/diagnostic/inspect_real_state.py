"""
scripts/diagnostic/inspect_real_state.py
Inspección en vivo de posiciones y órdenes para todas las cuentas en Bitunix.
"""
import asyncio
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from engine.execution.account_manager import AccountManager

async def inspect_real_state():
    am = AccountManager(dry_run=False)
    for acc in am.get_all_accounts(enabled_only=True):
        ex = am.get_executor(acc.account_id)
        pos = await ex.get_pending_positions()
        orders = await ex.get_pending_orders()
        margin = await ex.get_available_margin_usdt()
        print(f"=== CUENTA: {acc.account_id} ({acc.label}) ===")
        print(f"Margen disponible: {margin:.2f} USDT")
        print(f"Posiciones abiertas ({len(pos)}):")
        for p in pos:
            sym = p.get('symbol')
            print(f"  -> POS: {sym} {p.get('side')} Qty:{p.get('qty')} Entry:{p.get('avgOpenPrice')} U_PnL:{p.get('unrealizedPNL')} R_PnL:{p.get('realizedPNL')}")
        print(f"Ordenes pendientes ({len(orders)}):")
        for o in orders:
            sym = o.get('symbol')
            side = o.get('side')
            px = o.get('price')
            qty = o.get('amount') or o.get('qty')
            print(f"  -> {sym} {side} Price:{px} Qty:{qty}")

if __name__ == '__main__':
    asyncio.run(inspect_real_state())
