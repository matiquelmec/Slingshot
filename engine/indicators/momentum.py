import pandas as pd
import numpy as np

# Intentar importar pandas_ta. Si no está, usar cálculos manuales optimizados.
try:
    import pandas_ta as ta
    HAS_PANDAS_TA = True
except ImportError:
    HAS_PANDAS_TA = False
    print("⚠️ 'pandas_ta' no encontrado. Usando cálculos manuales para indicadores. Instala con: pip install pandas-ta")

def calculate_rsi(df: pd.DataFrame, period=14) -> pd.DataFrame:
    """Relative Strength Index (Criptodamus Herencia)."""
    df = df.copy()
    if HAS_PANDAS_TA:
        df['rsi'] = df.ta.rsi(length=period)
    else:
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
    # Detectar zonas extremas
    df['rsi_oversold'] = df['rsi'] < 30
    df['rsi_overbought'] = df['rsi'] > 70
    return df

def calculate_macd(df: pd.DataFrame, fast=12, slow=26, signal=9) -> pd.DataFrame:
    """MACD - Moving Average Convergence Divergence."""
    df = df.copy()
    if HAS_PANDAS_TA:
        macd_df = df.ta.macd(fast=fast, slow=slow, signal=signal)
        df['macd_line'] = macd_df[f'MACD_{fast}_{slow}_{signal}']
        df['macd_signal'] = macd_df[f'MACDs_{fast}_{slow}_{signal}']
        df['macd_hist'] = macd_df[f'MACDh_{fast}_{slow}_{signal}']
    else:
        ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
        ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
        df['macd_line'] = ema_fast - ema_slow
        df['macd_signal'] = df['macd_line'].ewm(span=signal, adjust=False).mean()
        df['macd_hist'] = df['macd_line'] - df['macd_signal']
        
    # Cruce alcista (línea azul cruza hacia arriba la naranja)
    df['macd_bullish_cross'] = (df['macd_line'] > df['macd_signal']) & (df['macd_line'].shift(1) <= df['macd_signal'].shift(1))
    return df

def calculate_bbwp(df: pd.DataFrame, period=252, basis_period=20) -> pd.DataFrame:
    """
    Bollinger Band Width Percentile (BBWP)
    Detecta Squeeze (compresión) del precio.
    Si BBWP < 20, el mercado está comprimido y a punto de explotar (Ideal tras un Barrido de Liquidez).
    Nota: Reducimos el periodo por defecto para data intradía (252 es para daily).
    """
    df = df.copy()
    # 1. Calcular Ancho de Bandas de Bollinger (BBW)
    sma = df['close'].rolling(window=basis_period).mean()
    std = df['close'].rolling(window=basis_period).std()
    upper_band = sma + (std * 2)
    lower_band = sma - (std * 2)
    bbw = (upper_band - lower_band) / sma
    
    # 2. Calcular el Percentil del BBW en la ventana histórica
    # El % de veces que el BBW actual ha sido mayor que los BBWs pasados en el periodo
    bbwp = bbw.rolling(window=period).apply(
        lambda x: (pd.Series(x).rank(pct=True).iloc[-1]) * 100, 
        raw=False
    )
    
    df['bbwp'] = bbwp
    df['squeeze_active'] = df['bbwp'] < 20
    
    return df

def apply_criptodamus_suite(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica todos los indicadores clásicos heredados."""
    df = calculate_rsi(df)
    df = calculate_macd(df)
    
    # Adaptar ventana BBWP al intradía (en lugar de 252 velas diarias, usamos ≈ 2 días de velas de 15m)
    # 2 días * 24 horas * 4 velas/hora = 192 velas
    df = calculate_bbwp(df, period=192)
    
    return df

if __name__ == "__main__":
    import os
    from pathlib import Path
    
    file_path = Path(__file__).parent.parent.parent / "data" / "btcusdt_15m.parquet"
    if os.path.exists(file_path):
        data = pd.read_parquet(file_path)
        analyzed_data = apply_criptodamus_suite(data)
        
        # Filtrar convergencias poderosas (Ej: RSI Sobrevendido + MACD cruzando al alza + Squeeze)
        # (Para testear rápido, solo buscaremos RSI Sobrevendido + Squeeze activo)
        golden_setup = analyzed_data[analyzed_data['rsi_oversold'] & analyzed_data['squeeze_active']]
        
        print(f"🧬 Herencia de Criptodamus Integrada (RSI, MACD, BBWP)")
        print(f"Total de velas analizadas: {len(data)}")
        print(f"🔋 Zonas de Squeeze (Compresión Extrema BBWP < 20): {analyzed_data['squeeze_active'].sum()}")
        print(f"💎 Setups 'Golden' (RSI < 30 + Compresión): {len(golden_setup)} velas")
    else:
        print("Data file not found.")
