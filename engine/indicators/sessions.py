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
    
    # 1. Extraer los Máximos y Mínimos de Asia
    df['asian_high'] = df[asian_mask].groupby('trading_day')['high'].transform('max')
    df['asian_low'] = df[asian_mask].groupby('trading_day')['low'].transform('min')
    
    # 2. Extraer los Máximos y Mínimos de Londres
    df['london_high'] = df[london_mask].groupby('trading_day')['high'].transform('max')
    df['london_low'] = df[london_mask].groupby('trading_day')['low'].transform('min')

    # 2.5 Extraer los Máximos y Mínimos de Nueva York
    df['ny_high'] = df[ny_mask].groupby('trading_day')['high'].transform('max')
    df['ny_low'] = df[ny_mask].groupby('trading_day')['low'].transform('min')
    
    # --- ARREGLO DE PERSISTENCIA (Rolling Sessions) ---
    # Usamos ffill() para que si hoy aún no ha ocurrido la sesión (ej: Londres a las 00:00 UTC),
    # el sistema mantenga los niveles de la sesión de ayer en lugar de mostrar NaN.
    cols_to_fill = ['asian_high', 'asian_low', 'london_high', 'london_low', 'ny_high', 'ny_low']
    df[cols_to_fill] = df[cols_to_fill].ffill()
    
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
