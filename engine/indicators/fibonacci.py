import pandas as pd
import numpy as np

def calculate_fibonacci_retracements(high: float, low: float, uptrend: bool = True) -> dict:
    """
    Calcula los niveles clave de retroceso y extensión de Fibonacci dado un swing (High a Low).
    Niveles Clásicos Criptodamus: 0, 0.236, 0.382, 0.5, 0.618, 0.786, 1
    Golden Pocket Criptodamus: 0.618 - 0.66
    """
    diff = high - low
    levels = {}
    
    if uptrend:
        # Tendencia Alcista: El precio cae desde el High buscando soporte
        levels['0.0'] = high
        levels['0.236'] = high - (diff * 0.236)
        levels['0.382'] = high - (diff * 0.382)
        levels['0.5'] = high - (diff * 0.5)
        levels['0.618'] = high - (diff * 0.618)
        levels['0.66'] = high - (diff * 0.66) # Golden Pocket
        levels['0.786'] = high - (diff * 0.786)
        levels['1.0'] = low
    else:
        # Tendencia Bajista: El precio sube desde el Low buscando resistencia
        levels['0.0'] = low
        levels['0.236'] = low + (diff * 0.236)
        levels['0.382'] = low + (diff * 0.382)
        levels['0.5'] = low + (diff * 0.5)
        levels['0.618'] = low + (diff * 0.618)
        levels['0.66'] = low + (diff * 0.66) # Golden Pocket
        levels['0.786'] = low + (diff * 0.786)
        levels['1.0'] = high
        
    return levels

def identify_dynamic_fib_swing(df: pd.DataFrame, window: int = 40) -> pd.DataFrame:
    """
    Detecta automáticamente los Swing Highs y Swing Lows recientes para trazar el Fibonacci algorítmico.
    (Basado en la lógica de fractales o ventanas de tiempo).
    """
    df = df.copy()
    
    # Encontrar el Máximo (High) y Mínimo (Low) en la ventana lookback
    df['swing_high'] = df['high'].rolling(window=window).max()
    df['swing_low'] = df['low'].rolling(window=window).min()
    
    # Determinar si el último extremo fue un High o un Low para saber la dirección de la tendencia micro
    # (Muy simplificado para análisis vectorizado: Comparamos distancias)
    
    # Inicializar columnas del Golden Pocket
    df['fib_gp_top'] = np.nan
    df['fib_gp_bottom'] = np.nan
    df['isIn_GoldenPocket'] = False
    
    # Calcular el Golden Pocket de forma vectorizada (Asumiendo que retrocedemos desde el High reciente)
    # diff = Swing High - Swing Low
    diff = df['swing_high'] - df['swing_low']
    
    # Golden Pocket (0.618 - 0.66) para Pullbacks Alcistas (Buscando soporte después de subir)
    df['fib_gp_top'] = df['swing_high'] - (diff * 0.618)
    df['fib_gp_bottom'] = df['swing_high'] - (diff * 0.66)
    
    # Detectar si el precio de cierre actual está dentro de esa franja mágica
    df['in_golden_pocket'] = (df['close'] <= df['fib_gp_top']) & (df['close'] >= df['fib_gp_bottom'])
    
    return df

def _find_algo_pivots(df: pd.DataFrame, n_bars: int = 5):
    """
    Encuentra los Pivots High y Pivots Low matemáticos (Fractales) 
    revisando n_bars a la izquierda y n_bars a la derecha.
    Devuelve los dataframes filtrados solo con los pivots confirmados.
    """
    df_copy = df.copy()
    window_size = (n_bars * 2) + 1
    
    # max() iterando con center=True ubica el valor en el indice central (vela actual)
    df_copy['rolling_max'] = df_copy['high'].rolling(window=window_size, center=True).max()
    df_copy['rolling_min'] = df_copy['low'].rolling(window=window_size, center=True).min()
    
    is_pivot_high = (df_copy['high'] == df_copy['rolling_max']) & (df_copy['high'].notna())
    is_pivot_low =  (df_copy['low'] == df_copy['rolling_min']) & (df_copy['low'].notna())
    
    return df_copy[is_pivot_high], df_copy[is_pivot_low]

def _get_fibonacci_major_leg(df: pd.DataFrame, n_bars: int = 5, lookback_pivots: int = 15) -> dict | None:
    """Fallback: Filtra los últimos `lookback_pivots` para encontrar el Swing Mayor (Major Leg)."""
    pivot_highs, pivot_lows = _find_algo_pivots(df, n_bars)
    
    if pivot_highs.empty or pivot_lows.empty:
        return _fallback_fibonacci(df)
        
    recent_ph = pivot_highs.tail(lookback_pivots)
    recent_pl = pivot_lows.tail(lookback_pivots)
    
    major_ph_idx = recent_ph['high'].idxmax()
    major_pl_idx = recent_pl['low'].idxmin()
    
    major_ph_val = float(recent_ph.loc[major_ph_idx, 'high'])
    major_pl_val = float(recent_pl.loc[major_pl_idx, 'low'])
    
    is_uptrend_confirmed = major_pl_idx < major_ph_idx
    
    if is_uptrend_confirmed:
        recent_data = df.loc[major_ph_idx:]
        absolute_high = float(recent_data['high'].max())
        if absolute_high > major_ph_val:
            major_ph_val = absolute_high
            
        leg_data = df.loc[major_pl_idx:major_ph_idx]
        if not leg_data.empty:
            major_pl_val = float(leg_data['low'].min())
    else:
        recent_data = df.loc[major_pl_idx:]
        absolute_low = float(recent_data['low'].min())
        if absolute_low < major_pl_val:
            major_pl_val = absolute_low
            
        leg_data = df.loc[major_ph_idx:major_pl_idx]
        if not leg_data.empty:
            major_ph_val = float(leg_data['high'].max())

    final_is_uptrend = major_pl_idx < major_ph_idx
    
    if major_ph_val == major_pl_val:
        return None
        
    levels = calculate_fibonacci_retracements(high=major_ph_val, low=major_pl_val, uptrend=final_is_uptrend)
    return {
        "swing_high": major_ph_val,
        "swing_low": major_pl_val,
        "levels": levels
    }

def get_current_fibonacci_levels(df: pd.DataFrame, n_bars: int = 5) -> dict | None:
    """
    SMC God Mode (Macro Swing): Identifica la 'Major Leg' (Pierna Institucional Completa)
    filtrando micro-impulsos para evitar un Fibonacci hiperactivo.
    Traza la cuadrícula estricta desde el Pivot High Absoluto al Pivot Low Absoluto del ciclo.
    """
    # Usamos lookback de 20 pivots (aprox 1.5 a 3 días de data en 15m) para capturar el gran swing
    return _get_fibonacci_major_leg(df, n_bars=n_bars, lookback_pivots=20)

def _fallback_fibonacci(df: pd.DataFrame, window: int = 40) -> dict | None:
    """Implementación clásica estática de emergencia en caso de fallar el escáner fractal."""
    if len(df) < window:
        window = len(df)
        if window < 2:
            return None
            
    tail_df = df.tail(window)
    recent_high = float(tail_df['high'].max())
    recent_low = float(tail_df['low'].min())
    
    if recent_high == recent_low:
        return None
        
    high_idx = tail_df['high'].idxmax()
    low_idx = tail_df['low'].idxmin()
    is_uptrend = low_idx < high_idx
    
    levels = calculate_fibonacci_retracements(high=recent_high, low=recent_low, uptrend=is_uptrend)
    return {
        "swing_high": recent_high,
        "swing_low": recent_low,
        "levels": levels
    }

if __name__ == "__main__":
    import os
    from pathlib import Path
    
    file_path = Path(__file__).parent.parent.parent / "data" / "btcusdt_15m.parquet"
    if os.path.exists(file_path):
        data = pd.read_parquet(file_path)
        analyzed_data = identify_dynamic_fib_swing(data)
        
        # Filtrar cuántas velas tocaron el Golden Pocket
        gp_hits = analyzed_data[analyzed_data['in_golden_pocket']]
        
        print("📐 Módulo Fibonacci & Golden Pocket Activado")
        print(f"Total Velas Analizadas: {len(data)}")
        print(f"🔥 Impactos en el Golden Pocket (0.618 - 0.66): {len(gp_hits)} velas")
        
        if not gp_hits.empty:
            last_hit = gp_hits.iloc[-1]
            print(f"\nÚltima interacción con el Golden Pocket:")
            print(f"Fecha: {last_hit['timestamp']}")
            print(f"Precio: ${last_hit['close']}")
            print(f"Swing (Low ${last_hit['swing_low']} -> High ${last_hit['swing_high']})")
    else:
        print("Data file not found.")
