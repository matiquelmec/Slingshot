import pandas as pd
import numpy as np

def calculate_rvol(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """
    Relative Volume (RVOL) - Nivel 3 (Gatillo).
    Calcula si el volumen actual es inusualmente alto en comparación con el promedio reciente.
    RVOL > 1.5 a 2.0 indica fuerte interés institucional.
    """
    df = df.copy()
    
    # Calcular el Promedio Móvil Simple (SMA) del volumen
    df['vol_sma'] = df['volume'].rolling(window=window).mean()
    
    # Calcular RVOL = Volumen Actual / SMA del Volumen
    df['rvol'] = df['volume'] / df['vol_sma']
    
    # Limpiar posibles divisiones por cero o nulos tempranos
    df['rvol'] = df['rvol'].fillna(0)
    
    return df

def analyze_volume_trend(df: pd.DataFrame) -> pd.DataFrame:
    """
    Analiza la tendencia del volumen para confirmar si un movimiento de precio 
    está respaldado por dinero institucional (Volumen Creciente) o si es una 
    trampa (Volumen Decreciente).
    """
    df = df.copy()
    
    # Comparar volumen de la vela actual con la anterior
    df['vol_increasing'] = df['volume'] > df['volume'].shift(1)
    
    # Detectar picos anómalos (Climax Volume) - Por encima del percentil 95
    # Usamos una ventana de 50 velas previas (aprox 12 horas en velas de 15m)
    rolling_95th = df['volume'].rolling(window=50).quantile(0.95)
    df['is_climax_vol'] = df['volume'] > rolling_95th
    
    return df

def confirm_trigger(df: pd.DataFrame, min_rvol: float = 1.5) -> pd.DataFrame:
    """
    El Gatillo Final (SMC Nivel 3).
    Si estamos en un Order Block, necesitamos que el RVOL sea alto (institucional)
    para confirmar la entrada.
    """
    df = calculate_rvol(df)
    df = analyze_volume_trend(df)
    
    # Columna maestra de confirmación de entrada
    df['valid_trigger'] = df['rvol'] >= min_rvol
    
    return df

if __name__ == "__main__":
    import os
    from pathlib import Path
    
    file_path = Path(__file__).parent.parent.parent / "data" / "btcusdt_15m.parquet"
    if os.path.exists(file_path):
        data = pd.read_parquet(file_path)
        analyzed_data = confirm_trigger(data)
        
        # Filtrar velas con RVOL Extremo (> 2.5x lo normal)
        extreme_vol = analyzed_data[analyzed_data['rvol'] >= 2.5]
        
        print("📊 Nivel 3: Escáner de Volumen Institucional (RVOL):")
        print(f"Total de velas analizadas: {len(data)}")
        print(f"🔥 Velas con inyección extrema de capital (RVOL >= 2.5): {len(extreme_vol)}")
    else:
        print("Data file not found.")
