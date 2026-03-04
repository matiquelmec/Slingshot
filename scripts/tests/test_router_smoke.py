
import sys
import os
from pathlib import Path
import pandas as pd
import json

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from engine.main_router import SlingshotRouter

def run_diagnostic():
    print("--- Starting Engine Diagnostic ---")
    try:
        router = SlingshotRouter()
        print("Successfully instantiated SlingshotRouter")
        
        # Create dummy data
        data = {
            'timestamp': pd.date_range(start='2024-01-01', periods=300, freq='15min'),
            'open': [50000.0] * 300,
            'high': [50100.0] * 300,
            'low': [49900.0] * 300,
            'close': [50050.0] * 300,
            'volume': [100.0] * 300
        }
        df = pd.DataFrame(data)
        
        print(f"Sample data created with {len(df)} rows")
        
        result = router.process_market_data(df, asset="BTCUSDT", interval="15m")
        print("Successfully processed market data")
        print(f"Result keys: {list(result.keys())}")
        print(f"Market Regime: {result.get('market_regime')}")
        print(f"Active Strategy: {result.get('active_strategy')}")
        
    except Exception as e:
        print(f"DIAGNOSTIC FAILED: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_diagnostic()
