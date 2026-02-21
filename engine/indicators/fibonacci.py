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
