import sys
import os
import pandas as pd
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.backtest.unified_backtest_engine import UnifiedBacktestEngine, DATA_DIR

def run_comparative_matrix():
    btc_map = UnifiedBacktestEngine()._load_btc_macro_map()
    
    # Test 1: Baseline actual (min_score=50, todos los activos)
    engine_base = UnifiedBacktestEngine(min_confluence_score=50)
    
    # Test 2: Confluence Institucional (min_score=60)
    engine_60 = UnifiedBacktestEngine(min_confluence_score=60)
    
    # Test 3: Confluence Elite (min_score=65)
    engine_65 = UnifiedBacktestEngine(min_confluence_score=65)

    # Universo A (Sin podar): Todos los 14 activos
    mega_a = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "AVAXUSDT", "LINKUSDT", "XRPUSDT"]
    alts_a = ["RENDERUSDT", "SUIUSDT", "INJUSDT", "NEARUSDT", "FETUSDT", "ATOMUSDT", "BNBUSDT", "PAXGUSDT"]

    # Universo B (Portafolio Alpha Optimizado): Solo activos validados matemáticamente
    mega_b = ["ETHUSDT", "LINKUSDT", "PAXGUSDT"]
    alts_b = ["SUIUSDT", "RENDERUSDT", "ATOMUSDT", "TIAUSDT", "FETUSDT", "NEARUSDT", "ADAUSDT", "DOGEUSDT"]

    configs = [
        ("1. Baseline Sin Podar (Score >= 50)", engine_base, mega_a, alts_a),
        ("2. Filtro Institucional (Score >= 60)", engine_60, mega_a, alts_a),
        ("3. Filtro Elite (Score >= 65)", engine_65, mega_a, alts_a),
        ("4. Portafolio Alpha (Score >= 60 + Sweet Spot)", engine_60, mega_b, alts_b),
        ("5. Portafolio Alpha Elite (Score >= 65 + Sweet Spot)", engine_65, mega_b, alts_b),
    ]

    summary = []

    for label, eng, megas, alts in configs:
        res = []
        for sym in megas:
            t = eng.run_single_asset(sym, interval="1h", btc_map=btc_map)
            res.extend(t)
        for sym in alts:
            t = eng.run_single_asset(sym, interval="15m", btc_map=btc_map)
            res.extend(t)
            
        df = pd.DataFrame(res)
        if df.empty:
            continue
            
        trades = len(df)
        winners = df[df['outcome_r'] > 0]
        losers = df[df['outcome_r'] < 0]
        be = df[df['outcome_r'] == 0]
        
        wr = len(winners) / trades * 100
        be_rate = len(be) / trades * 100
        total_r = df['outcome_r'].sum()
        gross_w = winners['outcome_r'].sum() if len(winners)>0 else 0
        gross_l = abs(losers['outcome_r'].sum()) if len(losers)>0 else 1
        pf = gross_w / gross_l if gross_l > 0 else 99
        
        # Max Drawdown
        df['pnl_usd'] = df['outcome_r'] * 1000.0
        df['cum'] = df['pnl_usd'].cumsum()
        df['equity'] = 100000.0 + df['cum']
        df['dd'] = (df['equity'] - df['equity'].cummax()) / df['equity'].cummax() * 100
        max_dd = abs(df['dd'].min())

        summary.append({
            "Configuración": label,
            "Trades": trades,
            "Win Rate": f"{wr:.1f}%",
            "BE Rate": f"{be_rate:.1f}%",
            "Retorno Total": f"{total_r:+.2f} R",
            "Profit Factor": f"{pf:.2f}",
            "Max Drawdown": f"-{max_dd:.2f}%"
        })

    print("="*95)
    print("🔬 MATRIZ COMPARATIVA DE OPTIMIZACIÓN CUANTITATIVA SLINGSHOT")
    print("="*95)
    print(pd.DataFrame(summary).to_string(index=False))

if __name__ == "__main__":
    run_comparative_matrix()
