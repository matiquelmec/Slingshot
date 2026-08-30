"""
scripts/manage_open_positions.py
=============================================================================
AUDITORIA Y GESTION EN VIVO DE POSICIONES ABIERTAS EN BITUNIX
=============================================================================
Consulta las posiciones abiertas en tu cuenta de Bitunix, calcula la ganancia
flotante en unidades R y ejecuta de inmediato el Fast BE (+1.0R) para proteger
el capital al 100% en el exchange.
"""
import sys
import os
import asyncio

# Configurar encoding UTF-8 en Windows stdout
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.workers.trade_manager import trade_manager
from engine.execution.bitunix_executor import BitunixExecutor
from engine.core.logger import logger

async def main():
    print("\n" + "="*85)
    print("[SLINGSHOT v21.0] AUDITORIA Y GESTION EN VIVO DE POSICIONES EN BITUNIX")
    print("="*85)

    bitunix = BitunixExecutor()
    balance = await bitunix.get_balance()
    print(f"Balance Disponible en Bitunix: ${balance:,.2f} USDT")
    print(f"Modo de Ejecucion: {'DRY RUN (Simulacion)' if bitunix.dry_run else 'LIVE EXCHANGE (Real)'}")
    print("-"*85)

    managed_positions = await trade_manager.sync_live_bitunix_positions()

    if not managed_positions:
        print("\n[INFO] No se detectaron posiciones abiertas pendientes en Bitunix en este momento.")
        print("El motor TradeManager continuara vigilando en segundo plano cada 30 segundos.\n")
        return

    print(f"\n{'ACTIVO':<12} | {'LADO':<10} | {'ENTRADA':<12} | {'ACTUAL':<12} | {'SL ACTUAL':<12} | {'PNL (R)':<8} | {'ESTADO':<18} | {'ACCION':<20}")
    print("-" * 115)
    for p in managed_positions:
        side_str = "LONG" if p["side"] == "LONG" else "SHORT"
        print(f"{p['symbol']:<12} | {side_str:<10} | ${p['entry_price']:<11,.4f} | ${p['current_price']:<11,.4f} | ${p['current_sl']:<11,.4f} | {p['r_profit']:+6.2f}R | {p['status']:<18} | {p['action']:<20}")
    print("-" * 115 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
