import sys
import os
import pandas as pd
import numpy as np

sys.path.append(os.getcwd())

from engine.router.analyzer import MarketAnalyzer
from engine.strategies.smc import SMCInstitutionalStrategy

df_full = pd.read_parquet('engine/tests/data/BTCUSDT_4h_90d.parquet')
df_full.rename(columns={'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume'}, inplace=True)
df_full['timestamp'] = pd.to_datetime(df_full['t'], unit='s')

analyzer = MarketAnalyzer()
smc = SMCInstitutionalStrategy()

window_size = 200
triggers = 0

for i in range(100, len(df_full)):
    start_w = max(0, i - window_size)
    window = df_full.iloc[start_w:i].copy().reset_index(drop=True)
    
    mm = analyzer.analyze(window, asset='BTCUSDT', interval='4h')
    analyzed = smc.analyze(mm.df_analyzed, interval='4h')
    opps = smc.find_opportunities(analyzed, asset='BTCUSDT')
    
    if opps:
        triggers += 1
        print(f"Trigger at {window['timestamp'].iloc[-1]}: {opps[0]['signal_type']}")

print(f"\nTotal triggers in loop: {triggers}")
