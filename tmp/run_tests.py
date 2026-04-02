import sys
import os
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stderr = sys.stdout
sys.path.insert(0, '.')

import pandas as pd
import numpy as np

rng = np.random.default_rng(42)
rows = 300
closes = 85000.0 + np.cumsum(rng.normal(0, 170, rows))
df = pd.DataFrame({
    'timestamp': pd.date_range('2024-01-01', periods=rows, freq='15min'),
    'open':   closes,
    'high':   closes + 85,
    'low':    closes - 85,
    'close':  closes,
    'volume': [500.0] * rows,
})

passed = 0
failed = 0


def run(name, fn):
    global passed, failed
    try:
        fn()
        passed += 1
    except Exception as e:
        import traceback
        print('FAIL [' + name + ']: ' + str(e))
        traceback.print_exc()
        failed += 1


def t1():
    from engine.router.analyzer import MarketAnalyzer
    mm = MarketAnalyzer().analyze(df.copy(), asset='BTCUSDT', interval='15m')
    assert mm.current_price > 0
    assert isinstance(mm.smc, dict)
    assert isinstance(mm.key_levels, dict)
    print('  PASS MarketAnalyzer | regime=' + mm.market_regime + ' | price=' + str(round(mm.current_price)))


def t2():
    from engine.router.analyzer import MarketAnalyzer
    from engine.router.dispatcher import build_base_result
    mm = MarketAnalyzer().analyze(df.copy())
    r = build_base_result(mm)
    assert 'signals' in r and 'smc' in r and 'market_regime' in r
    print('  PASS build_base_result | keys=' + str(len(r)))


def t3():
    from engine.router.dispatcher import enrich_signal
    sig = {'timestamp': '2024-01-01 00:15:00', 'price': 85000.0, 'type': 'LONG_OB'}
    risk = {
        'risk_amount_usdt': 50, 'risk_pct': 1, 'leverage': 5,
        'position_size_usdt': 5000, 'stop_loss': 84000,
        'take_profit_3r': 88000, 'entry_zone_top': 85100,
        'entry_zone_bottom': 84900, 'expiry_candles': 3,
    }
    e = enrich_signal(sig, risk, '15m')
    assert e['stop_loss'] == 84000 and e['leverage'] == 5
    exp = e.get('expiry_timestamp', 'N/A')
    print('  PASS enrich_signal | expiry=' + str(exp))


def t4():
    from engine.main_router import SlingshotRouter
    r = SlingshotRouter().process_market_data(df.copy(), asset='BTCUSDT', interval='15m', silent=True)
    assert isinstance(r, dict) and 'signals' in r and 'smc' in r
    print('  PASS SlingshotRouter | approved=' + str(len(r['signals'])) + ' | blocked=' + str(len(r['blocked_signals'])))


print('=' * 50)
print('SMOKE TEST --- SLINGSHOT v4.1 PLATINUM')
print('=' * 50)
run('MarketAnalyzer',    t1)
run('build_base_result', t2)
run('enrich_signal',     t3)
run('SlingshotRouter',   t4)
print('=' * 50)
print('RESULT: ' + str(passed) + '/' + str(passed + failed) + ' passed')
print('=' * 50)
sys.exit(failed)
