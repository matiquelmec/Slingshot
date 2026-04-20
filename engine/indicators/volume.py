from engine.core.logger import logger
import pandas as pd
import numpy as np
from scipy import stats

def _format_pandas_freq(interval: str) -> str:
    """Sanea el intervalo para compatibilidad con Pandas 2.2.0+"""
    if not interval: return None
    mapping = {'1m': '1min', '3m': '3min', '5m': '5min', '15m': '15min', '30m': '30min', '1h': '1h', '4h': '4h', '1d': '1D'}
    return mapping.get(interval, interval.replace('m', 'min') if interval.endswith('m') else interval)

def calculate_seasonal_volume(df: pd.DataFrame, window_days: int = 5) -> pd.Series:
    """
    Normalización por Estacionalidad v8.0 (Institutional Apex).
    Compara el volumen actual con el promedio histórico de su misma franja horaria.
    """
    if 'timestamp' not in df.columns or len(df) < 100:
        return pd.Series(df['volume'].median(), index=df.index)
    
    temp_df = df.copy()
    temp_df['dt'] = pd.to_datetime(temp_df['timestamp'], unit='ms', errors='coerce')
    temp_df['hour'] = temp_df['dt'].dt.hour
    temp_df['minute'] = temp_df['dt'].dt.minute
    
    # Calculamos cuántas muestras hay por slot
    slot_counts = temp_df.groupby(['hour', 'minute'])['volume'].transform('count')
    seasonal_profile = temp_df.groupby(['hour', 'minute'])['volume'].transform('mean')
    
    # Si tenemos menos de 2 muestras para un slot, la estacionalidad no es confiable
    # Usamos la mediana global del dataframe como fallback para esos slots
    global_median = temp_df['volume'].median()
    seasonal_profile = np.where(slot_counts >= 2, seasonal_profile, global_median)
    
    return pd.Series(seasonal_profile, index=df.index)

def calculate_rvol(df: pd.DataFrame, window: int = 50, use_seasonality: bool = True, target_interval: str = None) -> pd.DataFrame:
    """
    Relative Volume (RVOL) Apex Edition.
    Usa Rango Percentil (0-100) y Estacionalidad para una lectura no-lineal.
    """
    df = df.copy()
    if df.empty: return df

    # 1. Obtener Base de Comparación (Estacional o Mediana)
    if use_seasonality and 'timestamp' in df.columns:
        df['vol_median'] = calculate_seasonal_volume(df)
    else:
        df['vol_median'] = df['volume'].rolling(window=window, min_periods=20).median()
    
    # Asegurar que el median no sea ridículamente bajo (Protección Anti-Explosión)
    global_median = df['volume'].median()
    df['vol_median'] = df['vol_median'].replace(0, global_median)
    
    # 2. Ratio Crudo
    df['rvol_ratio'] = df['volume'] / (df['vol_median'] + 1e-9)
    
    # 3. Normalización por Rango Percentil (Robusto contra Outliers)
    # Indica qué tan alto es el volumen actual respecto al historial (0.0 a 1.0)
    df['rvol_pct'] = df['volume'].rolling(window=window*2, min_periods=20).rank(pct=True)
    
    # RVOL Final para el Dashboard (Escala Humana 0x - 5x)
    df['rvol'] = df['rvol_ratio'].clip(0, 5.0)
    
    return df

def calculate_absorption_index(df: pd.DataFrame, window: int = 50, target_interval: str = None) -> pd.DataFrame:
    """
    VSA Intelligence Engine v8.0.
    Mide 'Esfuerzo (Volumen)' vs 'Resultado (Precio)'.
    Escala: 0-100 (Donde > 80 es Absorción Extrema / Smart Money Accumulation).
    """
    df = df.copy()
    if len(df) < 20: return df

    # 1. Esfuerzo (Volumen Relativo)
    vol_median = df['volume'].rolling(window=window, min_periods=20).median()
    effort = df['volume'] / (vol_median + 1e-9)
    
    # 2. Resultado (Spread de la vela relativo a la volatilidad ATR)
    # Usamos ATR para que el "resultado" sea comparable en cualquier mercado/TF
    high_low = df['high'] - df['low']
    close_prev = df['close'].shift(1)
    tr = np.maximum(high_low, np.abs(df['high'] - close_prev), np.abs(df['low'] - close_prev))
    atr = pd.Series(tr).rolling(window=20).mean()
    
    body_spread = (df['close'] - df['open']).abs()
    result = body_spread / (atr + 1e-9)
    
    # 3. Índice de Absorción (Effort / Result)
    # Si hay mucho esfuerzo (vol) y poco resultado (cuerpo), hay absorción.
    # Añadimos un pequeño floor al result para evitar infinitos.
    absorption_raw = effort / (result + 0.1)
    
    # 4. Normalización Sigma Robusta (Z-Score MAD)
    median_abs = absorption_raw.rolling(window=window, min_periods=20).median()
    mad = (absorption_raw - median_abs).abs().rolling(window=window, min_periods=20).median()
    mad_scaled = (mad * 1.4826) + 1e-9
    
    z_score = (absorption_raw - median_abs) / mad_scaled
    
    # 5. Mapeo a Escala Apex (0-100)
    # Usamos una función sigmoide suave (0.15) para dar más recorrido y evitar saturación prematura.
    df['absorption_score'] = (1 / (1 + np.exp(-z_score * 0.15))) * 100
    
    # Metadatos para el Dashboard
    df['absorption_raw'] = absorption_raw
    
    return df

def analyze_volume_footprint(df: pd.DataFrame) -> pd.DataFrame:
    """Analiza la firma del volumen con lógica VSA."""
    df = df.copy()
    
    # 1. Detección de Clímax (Basado en Desviación Estándar Robusta)
    vol = df['volume']
    mean_vol = vol.rolling(window=50).mean()
    std_vol = vol.rolling(window=50).std()
    df['is_climax_vol'] = vol > (mean_vol + (std_vol * 2.5))
    
    # 2. Inyección de Inteligencia de Absorción
    df = calculate_absorption_index(df)
    
    return df

def confirm_trigger(df: pd.DataFrame, min_rvol_pct: float = 0.85) -> pd.DataFrame:
    """
    Gatillo Institucional Apex Edition.
    Valida si el volumen actual es parte de un movimiento orquestado por el Smart Money.
    """
    df = calculate_rvol(df)
    df = analyze_volume_footprint(df)
    
    # Filtro de Outliers destructivos
    vol_median = df['volume'].rolling(window=50).median()
    df['is_outlier_error'] = df['volume'] > (vol_median * 15.0) # Error de feed si es > 15x la mediana
    
    # Veredicto Apex:
    # 1. El volumen debe estar en el top 15% (Percentile Rank > 0.85)
    # 2. No debe ser un error de feed
    # 3. Debe haber una absorción significativa (> 70) o ser un Clímax validado.
    df['valid_trigger'] = (df['rvol_pct'] >= min_rvol_pct) & \
                          (~df['is_outlier_error']) & \
                          ((df['absorption_score'] > 70) | (df['is_climax_vol']))
    
    # Señales de Absorción de Elite para el Dashboard
    df['is_absorption_elite'] = (df['absorption_score'] > 85) & (df['rvol_pct'] > 0.70)
    
    return df

if __name__ == "__main__":
    import time
    start = time.time()
    
    # Simulación de estrés (1,000 velas)
    test_df = pd.DataFrame({
        'timestamp': pd.date_range(start='2024-01-01', periods=1000, freq='15min'),
        'open': np.random.uniform(50000, 51000, 1000),
        'high': np.random.uniform(51000, 52000, 1000),
        'low': np.random.uniform(49000, 50000, 1000),
        'close': np.random.uniform(50000, 51000, 1000),
        'volume': np.random.uniform(100, 1000, 1000)
    })
    
    result = confirm_trigger(test_df)
    
    end = time.time()
    logger.info(f"💎 [APEX] Kernel de Volumen v8.0 optimizado en {(end-start)*1000:.2f}ms")
    logger.info(f"Velas Elite detectadas: {len(result[result['is_absorption_elite']])}")
    if not result.empty:
        last = result.iloc[-1]
        logger.info(f"Estado Final -> RVOL Pct: {last['rvol_pct']:.2%}, Absorción: {last['absorption_score']:.2f}")
