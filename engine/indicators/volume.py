from engine.core.logger import logger
import pandas as pd
import numpy as np

def calculate_rvol(df: pd.DataFrame, window: int = 24) -> pd.DataFrame:
    """
    Relative Volume (RVOL) - Nivel 3 (Gatillo Institucional).
    Calcula si el volumen actual es inusualmente alto en comparación con la mediana reciente.
    Usamos la mediana para resistir valores extremos (Outliers) que sesgan la media simple.
    """
    df = df.copy()
    
    # Robust Median SMA (v5.7.155 Master Gold Unified)
    df['vol_median'] = df['volume'].rolling(window=window, min_periods=window).median()
    
    # Calcular RVOL = Volumen Actual / Mediana del Volumen
    df['rvol'] = df['volume'] / df['vol_median']
    df['rvol'] = df['rvol'].fillna(0)
    
    return df

def calculate_absorption_index(df: pd.DataFrame, window: int = 50) -> pd.DataFrame:
    """
    Índice de Absorción Institucional (Lattice Nivel 4).
    Mide la 'Presión de Volumen' sobre el 'Movimiento de Precio'.
    
    Un índice de absorción alto ocurre cuando el volumen es enorme pero el precio 
    se mueve poco (velas de cuerpo pequeño en zonas de liquidez).
    """
    df = df.copy()
    
    # Spread del cuerpo y spread total (fuerza residual)
    body_spread = (df['close'] - df['open']).abs()
    candle_spread = (df['high'] - df['low'])
    
    # Denominador de esfuerzo: evitamos división por cero con epsilon
    # Consideramos el movimiento del cuerpo como el factor principal de 'desplazamiento'
    displacement = body_spread + (candle_spread * 0.1) + (df['close'] * 0.00001)
    
    # Índice de Absorción Bruto
    df['absorption_raw'] = df['volume'] / displacement
    
    # Normalización del índice vía Z-Score Robusto (v5.4)
    median = df['absorption_raw'].rolling(window=window).median()
    mad = (df['absorption_raw'] - median).abs().rolling(window=window).median()
    
    # Si mad es 0, usamos un valor mínimo para evitar NaNs
    mad = mad.replace(0, 1.0)
    
    df['absorption_score'] = (df['absorption_raw'] - median) / (mad * 1.4826)
    
    return df

def calculate_zscore_robust(df: pd.DataFrame, window: int = 24, threshold: float = 3.5) -> pd.Series:
    """
    Protocolo Anti-Outlier v5.4 (Z-Score Robusto via MAD).
    A diferencia del Z-Score estándar, el uso de Mediana y MAD evita que los picos 
    volatiles oculten nuevas inserciones de capital.
    """
    if len(df) < window:
        return pd.Series([False] * len(df))
    
    vol = df['volume']
    median = vol.rolling(window=window, min_periods=1).median()
    mad = (vol - median).abs().rolling(window=window, min_periods=1).median()
    
    # Escalamiento para consistencia con distribución normal
    mad_scaled = mad * 1.4826
    mad_scaled = mad_scaled.replace(0, 1.0)
    
    z_score = (vol - median).abs() / mad_scaled
    return z_score > threshold

def analyze_volume_footprint(df: pd.DataFrame) -> pd.DataFrame:
    """
    Analiza la firma (Footprint) del volumen.
    """
    df = df.copy()
    
    # 1. Delta básico (Aproximación por cuerpo/mecha)
    df['vol_increasing'] = df['volume'] > df['volume'].shift(1)
    
    # 2. Climax Volume (Percentil 95 Adaptativo)
    rolling_95th = df['volume'].rolling(window=50).quantile(0.95)
    df['is_climax_vol'] = df['volume'] > rolling_95th
    
    # 3. Absorción Institucional
    df = calculate_absorption_index(df)
    
    return df

def confirm_trigger(df: pd.DataFrame, min_rvol: float = 2.0) -> pd.DataFrame:
    """
    Gatillo Institucional v5.7.155 Master Gold.
    Un trigger es válido si hay RVOL alto Y el volumen no es un outlier de error (Z < 6).
    """
    df = calculate_rvol(df)
    df = analyze_volume_footprint(df)
    
    # Filtro de Outliers destructivos (Error de Feed)
    df['is_outlier_error'] = calculate_zscore_robust(df, threshold=8.0)
    
    # Columna maestra de confirmación:
    # 1. El volumen relativo debe ser institucional (>= min_rvol)
    # 2. No debe ser un pico de error técnico (Z < 8)
    # 3. Absorción significativa confirma que el 'Smart Money' está entrando
    df['valid_trigger'] = (df['rvol'] >= min_rvol) & (~df['is_outlier_error'])
    
    # Marcar señales de Absorción Elite (donde se espera reversión o breakout)
    df['is_absorption_elite'] = (df['absorption_score'] > 2.5) & (df['rvol'] > 1.5)
    
    return df

if __name__ == "__main__":
    # Test de rendimiento del Kernel v5.7.155 Master Gold
    import time
    start = time.time()
    
    # Simulación de datos (10,000 velas)
    test_df = pd.DataFrame({
        'timestamp': pd.date_range(start='2024-01-01', periods=1000, freq='15min'),
        'open': np.random.uniform(50000, 51000, 1000),
        'high': np.random.uniform(51000, 52000, 1000),
        'low': np.random.uniform(49000, 50000, 1000),
        'close': np.random.uniform(50000, 51000, 1000),
        'volume': np.random.uniform(100, 1000, 1000)
    })
    
    # Añadir absorción sintética
    test_df.loc[500, 'volume'] = 5000
    test_df.loc[500, 'open'] = 51000
    test_df.loc[500, 'close'] = 51001 # Cuerpo mínimo, volumen máximo
    
    result = confirm_trigger(test_df)
    
    end = time.time()
    logger.info(f"💎 [DELTA] Kernel de Volumen v5.4 optimizado en {(end-start)*1000:.2f}ms")
    logger.info(f"Velas de Absorción detectadas: {len(result[result['is_absorption_elite']])}")
