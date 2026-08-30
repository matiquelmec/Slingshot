import os
import sys
import pandas as pd
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT_DIR))

from scripts.compare_ote_depth import ParametricOteEngine
from engine.backtest.unified_backtest_engine import UnifiedBacktestEngine, DATA_DIR

engine = ParametricOteEngine(min_confluence_score=60, mega_mult=0.382, alt_mult=0.295)
btc_map = UnifiedBacktestEngine()._load_btc_macro_map()

MASTER_ASSETS = [
    'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'AVAXUSDT', 'LINKUSDT', 'XRPUSDT', 'BNBUSDT', 'PAXGUSDT',
    'SUIUSDT', 'INJUSDT', 'RENDERUSDT', 'FETUSDT', 'NEARUSDT', 'ATOMUSDT', 'TIAUSDT'
]

results = []
for sym in MASTER_ASSETS:
    try:
        trades = engine.run_custom_asset(sym, interval='15m', btc_map=btc_map)
        df = pd.DataFrame(trades)
        if not df.empty:
            wins = df[df['outcome_r'] > 0]
            bes = df[df['outcome_r'] == 0]
            losses = df[df['outcome_r'] < 0]
            tot_r = df['outcome_r'].sum()
            gw = wins['outcome_r'].sum() if len(wins) > 0 else 0
            gl = abs(losses['outcome_r'].sum()) if len(losses) > 0 else 1
            pf = (gw / gl) if gl > 0 else 99.0
            wr = (len(wins) / len(df)) * 100
            be_r = (len(bes) / len(df)) * 100
            results.append({
                'asset': sym,
                'trades': len(df),
                'wr': wr,
                'be_r': be_r,
                'eff': wr + be_r,
                'ret_r': tot_r,
                'pf': pf
            })
    except Exception as e:
        print(f"Error {sym}:", e)

res_df = pd.DataFrame(results).sort_values('ret_r', ascending=False).reset_index(drop=True)
print("=" * 95)
print("🏆 RANKING INSTITUCIONAL FILTRADO (CONFLUENCIA >= 60 + OTE 70.5% + BTC MAP)")
print("=" * 95)
print(f"{'#':<3} {'ACTIVO':<10} {'TRADES':<8} {'WIN RATE':<10} {'BE RATE':<10} {'EFECTIVIDAD':<12} {'RETORNO (R)':<14} {'PROFIT FACTOR':<12}")
print("-" * 95)
for idx, r in res_df.iterrows():
    print(f"{idx+1:<3} {r['asset']:<10} {r['trades']:<8} {r['wr']:>5.1f}%     {r['be_r']:>5.1f}%     {r['eff']:>5.1f}%       {r['ret_r']:>+7.2f} R       {r['pf']:>5.2f}")
print("=" * 95)
tot_t = res_df['trades'].sum()
tot_r = res_df['ret_r'].sum()
avg_pf = res_df['pf'].mean()
print(f"📊 TOTAL CARTERA COMBINADA: {tot_t} trades | Retorno Total: {tot_r:+.2f} R | Profit Factor Promedio: {avg_pf:.2f}")
print("=" * 95)
