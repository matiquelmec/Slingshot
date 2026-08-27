import sys
import os
import glob
import pandas as pd
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.backtest.unified_backtest_engine import UnifiedBacktestEngine, DATA_DIR

def audit_all():
    engine = UnifiedBacktestEngine()
    btc_map = engine._load_btc_macro_map()
    
    # Get all symbols available in DATA_DIR
    files = glob.glob(os.path.join(DATA_DIR, "*_15m_180d.parquet"))
    symbols = sorted(list(set([os.path.basename(f).split("_")[0] for f in files])))
    
    print(f"Total Symbols in Parquet DB: {len(symbols)} -> {symbols}")
    
    results_15m = []
    results_1h = []
    
    for sym in symbols:
        res_15 = engine.run_single_asset(sym, interval="15m", btc_map=btc_map)
        if res_15:
            df = pd.DataFrame(res_15)
            r = df['outcome_r'].sum()
            wr = (df['outcome_r'] > 0).mean() * 100
            pf = df[df['outcome_r']>0]['outcome_r'].sum() / abs(df[df['outcome_r']<0]['outcome_r'].sum()) if (df['outcome_r']<0).sum() != 0 else 99
            results_15m.append({'symbol': sym, 'trades': len(df), 'win_rate': wr, 'retorno_r': r, 'profit_factor': pf})
            
        res_1h = engine.run_single_asset(sym, interval="1h", btc_map=btc_map)
        if res_1h:
            df = pd.DataFrame(res_1h)
            r = df['outcome_r'].sum()
            wr = (df['outcome_r'] > 0).mean() * 100
            pf = df[df['outcome_r']>0]['outcome_r'].sum() / abs(df[df['outcome_r']<0]['outcome_r'].sum()) if (df['outcome_r']<0).sum() != 0 else 99
            results_1h.append({'symbol': sym, 'trades': len(df), 'win_rate': wr, 'retorno_r': r, 'profit_factor': pf})
            
    print("\n" + "="*80)
    print("🏆 AUDITORÍA 15M (SCALP) DE TODOS LOS ACTIVOS:")
    print("="*80)
    df_15 = pd.DataFrame(results_15m).sort_values('retorno_r', ascending=False)
    print(df_15.to_string(index=False))
    
    print("\n" + "="*80)
    print("🏆 AUDITORÍA 1H (SWING) DE TODOS LOS ACTIVOS:")
    print("="*80)
    df_1h = pd.DataFrame(results_1h).sort_values('retorno_r', ascending=False)
    print(df_1h.to_string(index=False))

if __name__ == "__main__":
    audit_all()
