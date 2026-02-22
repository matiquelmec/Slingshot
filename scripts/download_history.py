import requests
import pandas as pd
import time
from datetime import datetime
from pathlib import Path
import os

def download_binance_klines(symbol: str, interval: str, target_candles: int, output_file: Path):
    """
    Descarga data histórica de Binance iterando hacia atrás en el tiempo.
    """
    print(f"🚀 Iniciando descarga de historia para {symbol} ({interval})")
    print(f"🎯 Meta: {target_candles} velas (Aprox. 1 año en 15m)")
    
    base_url = "https://api.binance.com/api/v3/klines"
    
    # Binance limit per request
    limit = 1000 
    
    all_klines = []
    
    # We start from current time backwards
    end_time = int(time.time() * 1000)
    
    calls_made = 0
    while len(all_klines) < target_candles:
        # Prevent rate limit bans
        if calls_made > 0 and calls_made % 10 == 0:
            time.sleep(1)
            
        params = {
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": limit,
            "endTime": end_time
        }
        
        try:
            response = requests.get(base_url, params=params)
            response.raise_for_status()
            data = response.json()
            calls_made += 1
            
            if not data:
                print("⚠️ Binance no devolvió más datos. Alcanzamos el límite histórico.")
                break
                
            # data comes ordered chronological (oldest to newest in the chunk)
            # Since we requested up to end_time, the last candle in 'data' is the newest one.
            # We must prepend these to our list because we are querying backwards.
            all_klines = data + all_klines
            
            # Update end_time to be 1 millisecond BEFORE the oldest candle in the current chunk
            oldest_candle_open_time = data[0][0]
            end_time = oldest_candle_open_time - 1
            
            print(f"📥 Descargadas {len(all_klines)} de {target_candles} velas. "
                  f"Fecha oldest: {datetime.fromtimestamp(oldest_candle_open_time/1000).strftime('%Y-%m-%d %H:%M')}")
                  
            if len(data) < limit:
                # Si nos devolvió menos del límite, significa que es todo lo que la API tiene
                print("⚠️ No hay más datos disponibles en el exchange para este rango temporal.")
                break
                
        except Exception as e:
            print(f"❌ Error al conectar con Binance: {e}")
            break
            
    # Keep only the target amount if we overshot
    if len(all_klines) > target_candles:
        all_klines = all_klines[-target_candles:]
        
    print("\n🛠️ Procesando y formateando datos para el Engine...")
    
    # Structuring like our current system expects
    df = pd.DataFrame(all_klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'number_of_trades',
        'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
    ])
    
    # Cleanup formats
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df['open'] = df['open'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['close'] = df['close'].astype(float)
    df['volume'] = df['volume'].astype(float)
    df['number_of_trades'] = df['number_of_trades'].astype(int)
    
    # Select only what we need
    df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume', 'number_of_trades']]
    
    # Guardar en parquet
    os.makedirs(output_file.parent, exist_ok=True)
    
    print(f"💾 Guardando dataset ultracomprimido: {output_file}")
    df.to_parquet(output_file, index=False)
    
    print(f"✅ ¡Descarga exitosa! Dataset final: {len(df)} filas.")
    print(f"   Rango de Fechas: {df['timestamp'].min()} hasta {df['timestamp'].max()}")

if __name__ == "__main__":
    # Configurar
    symbol = "BTCUSDT"
    interval = "15m"
    target_candles = 35000  # Aprox 1 año (365 * 96)
    
    # Donde lo guardamos
    project_root = Path(__file__).parent.parent
    data_dir = project_root / "data"
    output_path = data_dir / f"{symbol.lower()}_{interval}_1YEAR.parquet"
    
    download_binance_klines(symbol, interval, target_candles, output_path)
