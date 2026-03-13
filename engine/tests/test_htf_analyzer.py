import pandas as pd
import numpy as np
from engine.indicators.htf_analyzer import HTFAnalyzer

def generate_mock_df(direction='bullish', length=200):
    """Genera un DataFrame falso con tendencia clara."""
    data = []
    price = 50000.0
    for i in range(length):
        if direction == 'bullish':
            price += np.random.uniform(-10, 30)
        else:
            price += np.random.uniform(-30, 10)
        
        data.append({
            "timestamp": i * 3600 if length == 200 else i * 14400,
            "open": price - 10,
            "high": price + 20,
            "low": price - 20,
            "close": price,
            "volume": 1000
        })
    df = pd.DataFrame(data)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
    return df

def test_bullish_bias():
    analyzer = HTFAnalyzer()
    df_h4 = generate_mock_df('bullish', 250)
    df_h1 = generate_mock_df('bullish', 250)
    
    bias = analyzer.analyze_bias(df_h4, df_h1)
    print(f"\nTEST BULLISH: Direction={bias.direction}, Strength={bias.strength}, Reason={bias.reason}")
    assert bias.direction == 'BULLISH'

def test_bearish_bias():
    analyzer = HTFAnalyzer()
    df_h4 = generate_mock_df('bearish', 250)
    df_h1 = generate_mock_df('bearish', 250)
    
    bias = analyzer.analyze_bias(df_h4, df_h1)
    print(f"\nTEST BEARISH: Direction={bias.direction}, Strength={bias.strength}, Reason={bias.reason}")
    assert bias.direction == 'BEARISH'

if __name__ == "__main__":
    try:
        test_bullish_bias()
        test_bearish_bias()
        print("\n✅ HTFAnalyzer Unit Tests PASSED.")
    except Exception as e:
        print(f"\n❌ HTFAnalyzer Unit Tests FAILED: {e}")
