import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import asyncio
from engine.execution.account_manager import AccountManager

async def run():
    mgr = AccountManager()
    acc = mgr.get_account('cliente_2')
    if acc:
        acc.enabled = True
        mgr.save_accounts()
        print('cliente_2 enabled: True')
        
    ex = mgr.get_executor('cliente_2')
    pos = await ex.get_pending_positions()
    
    # 1. ETHUSDT (0.382 ETH)
    eth = next((p for p in (pos or []) if p.get('symbol') == 'ETHUSDT'), None)
    if eth:
        print('Setting TPs for ETH...')
        for p, q in [(2481.44, '0.229'), (2510.00, '0.076'), (2539.33, '0.038')]:
            b = {'symbol': 'ETHUSDT', 'qty': q, 'price': str(p), 'side': 'SELL', 'tradeSide': 'CLOSE', 'orderType': 'LIMIT', 'effect': 'GTC'}
            r = await ex._request('POST', '/api/v1/futures/trade/place_order', json_body=b)
            print('  ETH TP:', p, q, r.get('msg'))

    # 2. NEARUSDT (81 NEAR)
    near = next((p for p in (pos or []) if p.get('symbol') == 'NEARUSDT'), None)
    if near:
        print('Setting TPs for NEAR...')
        for p, q in [(2.279, '49'), (2.360, '16'), (2.468, '8')]:
            b = {'symbol': 'NEARUSDT', 'qty': q, 'price': str(p), 'side': 'SELL', 'tradeSide': 'CLOSE', 'orderType': 'LIMIT', 'effect': 'GTC'}
            r = await ex._request('POST', '/api/v1/futures/trade/place_order', json_body=b)
            print('  NEAR TP:', p, q, r.get('msg'))

    # 3. CLUSDT (4.6 CL)
    cl = next((p for p in (pos or []) if p.get('symbol') == 'CLUSDT'), None)
    if cl:
        print('Setting TPs for CL...')
        for p, q in [(93.56, '2.8'), (96.02, '0.9'), (99.30, '0.5')]:
            b = {'symbol': 'CLUSDT', 'qty': q, 'price': str(p), 'side': 'SELL', 'tradeSide': 'CLOSE', 'orderType': 'LIMIT', 'effect': 'GTC'}
            r = await ex._request('POST', '/api/v1/futures/trade/place_order', json_body=b)
            print('  CL TP:', p, q, r.get('msg'))

asyncio.run(run())
