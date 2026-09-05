import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import asyncio
from engine.execution.account_manager import AccountManager

async def run():
    mgr = AccountManager()
    ex = mgr.get_executor('cliente_2')
    pos = await ex.get_pending_positions()
    
    # 1. ETHUSDT (0.382 ETH @ 2456.63) -> PosId: 552934383104417917
    # Set TP @ 2481.44 and SL @ 2440.09
    eth = next((p for p in (pos or []) if p.get('symbol') == 'ETHUSDT'), None)
    if eth:
        p_id = eth.get('positionId')
        print(f'Configurando TP/SL oficial para ETH (PosId: {p_id})...')
        r = await ex.place_position_tpsl('ETHUSDT', p_id, sl_price=2440.09, tp_price=2481.44)
        print('  ETH TPSL:', r)

    # 2. NEARUSDT (81 NEAR @ 2.197) -> PosId: 2538598662386123783
    # Set TP @ 2.279 and SL @ 2.144
    near = next((p for p in (pos or []) if p.get('symbol') == 'NEARUSDT'), None)
    if near:
        p_id = near.get('positionId')
        print(f'Configurando TP/SL oficial para NEAR (PosId: {p_id})...')
        r = await ex.place_position_tpsl('NEARUSDT', p_id, sl_price=2.144, tp_price=2.279)
        print('  NEAR TPSL:', r)

    # 3. CLUSDT (4.6 CL @ 91.10) -> PosId: 8306061455399387501
    # Set TP @ 93.56 and SL @ 91.33
    cl = next((p for p in (pos or []) if p.get('symbol') == 'CLUSDT'), None)
    if cl:
        p_id = cl.get('positionId')
        print(f'Configurando TP/SL oficial para CL (PosId: {p_id})...')
        r = await ex.place_position_tpsl('CLUSDT', p_id, sl_price=91.33, tp_price=93.56)
        print('  CL TPSL:', r)

asyncio.run(run())
