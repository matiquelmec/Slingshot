import pandas as pd
import sys
from pathlib import Path

# Añadir ruta del proyecto
sys.path.append(str(Path(__file__).parent.parent))

from engine.indicators.structure import identify_order_blocks

def extract_order_blocks(df: pd.DataFrame) -> list:
    """Extrae las coordenadas exactas de los Order Blocks para el Frontend"""
    analyzed_df = identify_order_blocks(df)
    obs = []
    
    # Recorrer el dataframe buscando OBs confirmados
    for index, row in analyzed_df.iterrows():
        # Validar si hay OB Alcista (Bullish OB)
        if row.get('ob_bullish') == True:
            # En nuestro algoritmo actual, el OB es la vela ANTERIOR al imbalance.
            # Por lo tanto, necesitamos las coordenadas de la vela en el índice [i-1] (la vela índice).
            # No obstante, pandas iterrows es lento, necesitamos un shift previo o buscar por indice.
            pass

    return obs

if __name__ == "__main__":
    file_path = Path(__file__).parent.parent / "data" / "btcusdt_15m.parquet"
    if file_path.exists():
        data = pd.read_parquet(file_path).tail(100) # Últimas 100 velas
        print("Probando extracción de coordenadas OB...")
        
        # Test the implementation...
        
    else:
        print("Data no encontrada.")
