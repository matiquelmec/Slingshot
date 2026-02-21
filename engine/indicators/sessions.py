import pandas as pd

def map_sessions_liquidity(df: pd.DataFrame) -> pd.DataFrame:
    """
    Escáner de Liquidez por Sesión (SMC).
    Identifica los Máximos y Mínimos (Liquidity Pools) de las sesiones principales
    para detectar Sweeps (Cacería de Liquidez) institucional.
    Trabaja estrictamente con timestamps en UTC.
    """
    df = df.copy()
    
    if df['timestamp'].dt.tz is None:
        df['timestamp'] = df['timestamp'].dt.tz_localize('UTC')
    else:
        df['timestamp'] = df['timestamp'].dt.tz_convert('UTC')
        
    # Establecer el día de trading
    df['trading_day'] = df['timestamp'].dt.date
    df['hour'] = df['timestamp'].dt.hour
    
    # Definir los rangos de las sesiones (Horarios UTC)
    # Rango de Asia: 00:00 UTC a 06:00 UTC
    asian_mask = (df['hour'] >= 0) & (df['hour'] < 6)
    
    # Rango de Londres: 07:00 UTC a 15:00 UTC
    london_mask = (df['hour'] >= 7) & (df['hour'] < 15)
    
    # Rango de Nueva York: 13:00 UTC a 20:00 UTC
    ny_mask = (df['hour'] >= 13) & (df['hour'] < 20)
    
    # 1. Extraer los Máximos y Mínimos de Asia (El objetivo número 1 de Londres)
    asian_highs = df[asian_mask].groupby('trading_day')['high'].max()
    asian_lows = df[asian_mask].groupby('trading_day')['low'].min()
    
    df['asian_high'] = df['trading_day'].map(asian_highs)
    df['asian_low'] = df['trading_day'].map(asian_lows)
    
    # 2. Extraer los Máximos y Mínimos de Londres (El objetivo de Nueva York)
    london_highs = df[london_mask].groupby('trading_day')['high'].max()
    london_lows = df[london_mask].groupby('trading_day')['low'].min()
    
    df['london_high'] = df['trading_day'].map(london_highs)
    df['london_low'] = df['trading_day'].map(london_lows)

    # 2.5 Extraer los Máximos y Mínimos de Nueva York
    ny_highs = df[ny_mask].groupby('trading_day')['high'].max()
    ny_lows = df[ny_mask].groupby('trading_day')['low'].min()
    
    df['ny_high'] = df['trading_day'].map(ny_highs)
    df['ny_low'] = df['trading_day'].map(ny_lows)
    
    # 3. Extraer Previous Daily High/Low (PDH / PDL) - Objetivos Macro
    daily_highs = df.groupby('trading_day')['high'].max().shift(1) # Máximo del día anterior
    daily_lows = df.groupby('trading_day')['low'].min().shift(1)   # Mínimo del día anterior
    
    df['previous_daily_high'] = df['trading_day'].map(daily_highs)
    df['previous_daily_low'] = df['trading_day'].map(daily_lows)
    
    # 4. Detectar Sweeps (Barridos de Liquidez)
    # Por ejemplo, si en la sesión de Londres el precio supera el Asian High, es un "Liquidity Sweep"
    df['sweep_asian_high'] = df['high'] > df['asian_high']
    df['sweep_asian_low'] = df['low'] < df['asian_low']
    
    df['sweep_london_high'] = df['high'] > df['london_high']
    df['sweep_london_low'] = df['low'] < df['london_low']
    
    df['sweep_ny_high'] = df['high'] > df['ny_high']
    df['sweep_ny_low'] = df['low'] < df['ny_low']
    
    df['sweep_pdh'] = df['high'] > df['previous_daily_high']
    df['sweep_pdl'] = df['low'] < df['previous_daily_low']
    
    return df

if __name__ == "__main__":
    import os
    from pathlib import Path
    
    file_path = Path(__file__).parent.parent.parent / "data" / "btcusdt_15m.parquet"
    if os.path.exists(file_path):
        data = pd.read_parquet(file_path)
        analyzed_data = map_sessions_liquidity(data)
        
        # Filtramos para ver cuántas veces el mercado barrió la liquidez
        asian_sweeps_high = analyzed_data[analyzed_data['sweep_asian_high']]
        asian_sweeps_low = analyzed_data[analyzed_data['sweep_asian_low']]
        london_sweeps_high = analyzed_data[analyzed_data['sweep_london_high']]
        london_sweeps_low = analyzed_data[analyzed_data['sweep_london_low']]
        ny_sweeps_high = analyzed_data[analyzed_data['sweep_ny_high']]
        ny_sweeps_low = analyzed_data[analyzed_data['sweep_ny_low']]
        
        print("📊 Detección de Liquidez Institucional (Sweeps):")
        print(f"Total de velas analizadas: {len(data)}\n")
        print(f"🗡️ Barridos a Asia (High): {len(asian_sweeps_high)} | (Low): {len(asian_sweeps_low)}")
        print(f"🗡️ Barridos a Londres (High): {len(london_sweeps_high)} | (Low): {len(london_sweeps_low)}")
        print(f"🗡️ Barridos a Nueva York (High): {len(ny_sweeps_high)} | (Low): {len(ny_sweeps_low)}")
    else:
        print("Data file not found.")
