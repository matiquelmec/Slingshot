import pandas as pd
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from engine.strategies.smc import SMCInstitutionalStrategy
from engine.indicators.structure import identify_order_blocks

def find_golden_candles():
    print("[DIAGNOSTIC] Buscando señales en el dataset de 90 días...")
    data_file = "engine/tests/data/BTCUSDT_15m_90d.parquet"
    if not os.path.exists(data_file):
        print("Error: No data.")
        return
        
    df = pd.read_parquet(data_file)
    df.rename(columns={'t': 'timestamp', 'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume'}, inplace=True)
    
    # 1. Pre-procesar estructura
    df = identify_order_blocks(df)
    
    # 2. Correr Estrategia
    strategy = SMCInstitutionalStrategy()
    df = strategy.analyze(df)
    
    # Santa Trinidad: OB + Sweep + FVG
    long_mask = (df['recent_ob_bull'] & df['recent_sweep_bull'] & df['recent_fvg_bull'])
    short_mask = (df['recent_ob_bear'] & df['recent_sweep_bear'] & df['recent_fvg_bear'])
    
    gold_longs = df[long_mask]
    gold_shorts = df[short_mask]
    
    print(f"Total Velas: {len(df)}")
    print(f"Oportunidades LONG detectadas: {len(gold_longs)}")
    print(f"Oportunidades SHORT detectadas: {len(gold_shorts)}")
    
    if len(gold_longs) > 0:
        print("\nEjemplos de LONG (Timestamps):")
        print(gold_longs['timestamp'].tail(5).tolist())
        
    if len(gold_shorts) > 0:
        print("\nEjemplos de SHORT (Timestamps):")
        print(gold_shorts['timestamp'].tail(5).tolist())

if __name__ == "__main__":
    find_golden_candles()
