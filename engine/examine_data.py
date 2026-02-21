import pandas as pd
from pathlib import Path

def examine_data(symbol: str, interval: str):
    file_path = Path(__file__).parent.parent / "data" / f"{symbol.lower()}_{interval}.parquet"
    
    if not file_path.exists():
        print(f"Error: No se encontró el archivo {file_path}")
        return
        
    df = pd.read_parquet(file_path)
    
    print(f"\n{'='*50}")
    print(f"📊 DATA LAKE INSPECTION: {symbol} @ {interval}")
    print(f"{'='*50}")
    
    print(f"\nTotal de registros (velas): {len(df)}")
    print(f"Desde: {df['timestamp'].min()}")
    print(f"Hasta: {df['timestamp'].max()}")
    
    print("\nÚltimas 5 velas recibidas:")
    print("-" * 50)
    # Formateamos para que sea legible
    display_df = df.tail(5).copy()
    display_df['timestamp'] = display_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
    print(display_df.to_string(index=False))
    print(f"{'='*50}\n")

if __name__ == "__main__":
    examine_data("BTCUSDT", "15m")
