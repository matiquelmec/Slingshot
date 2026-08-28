import asyncio
import pandas as pd
import numpy as np
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from engine.backtest.unified_backtest_engine import UnifiedBacktestEngine, DATA_DIR

def run_oil_calibrated_tests():
    file_1h = os.path.join(DATA_DIR, "USOIL_1h_2y.parquet")
    if not os.path.exists(file_1h):
        print("No existe parquet de USOIL")
        return

    configs = [
        ("1. USOIL Baseline (Score >= 50)", UnifiedBacktestEngine(min_confluence_score=50)),
        ("2. USOIL Institucional (Score >= 60)", UnifiedBacktestEngine(min_confluence_score=60)),
        ("3. USOIL Elite (Score >= 65)", UnifiedBacktestEngine(min_confluence_score=65)),
        ("4. USOIL Sovereign (Score >= 70)", UnifiedBacktestEngine(min_confluence_score=70)),
    ]

    summary = []
    btc_map = UnifiedBacktestEngine()._load_btc_macro_map()

    for label, eng in configs:
        trades = eng.run_single_asset("USOIL", interval="1h", btc_map=btc_map)
        df_trades = pd.DataFrame(trades)
        if df_trades.empty:
            continue
        n_trades = len(df_trades)
        winners = df_trades[df_trades['outcome_r'] > 0]
        losers = df_trades[df_trades['outcome_r'] < 0]
        be = df_trades[df_trades['outcome_r'] == 0]
        
        wr = len(winners) / n_trades * 100
        be_rate = len(be) / n_trades * 100
        total_r = df_trades['outcome_r'].sum()
        gross_w = winners['outcome_r'].sum() if len(winners) > 0 else 0
        gross_l = abs(losers['outcome_r'].sum()) if len(losers) > 0 else 1
        pf = gross_w / gross_l if gross_l > 0 else 99.0

        summary.append({
            "Configuración": label,
            "Trades": n_trades,
            "Win Rate": f"{wr:.1f}%",
            "BE Rate": f"{be_rate:.1f}%",
            "Retorno Neto": f"{total_r:+.2f} R",
            "Profit Factor": f"{pf:.2f}"
        })

    print("\n" + "="*95)
    print("🛢️ CALIBRACIÓN EXPERIMENTAL: PETRÓLEO CRUDO (USOIL 1H / 2 AÑOS)")
    print("="*95)
    print(pd.DataFrame(summary).to_string(index=False))

if __name__ == "__main__":
    run_oil_calibrated_tests()
