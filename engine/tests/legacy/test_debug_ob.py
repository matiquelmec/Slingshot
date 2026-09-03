import pandas as pd
from pathlib import Path
from engine.indicators.structure import identify_order_blocks, extract_smc_coordinates

# Ruta dinámica para encontrar los datos de test
BASE_DIR = Path(__file__).parent
DATA_FILE = BASE_DIR / "data" / "BTCUSDT_15m_90d.parquet"

if not DATA_FILE.exists():
    # Fallback al directorio data raíz si no está en engine/tests/data
    DATA_FILE = Path(__file__).parent.parent.parent / "data" / "btcusdt_15m_1YEAR.parquet"

print(f"Loading test data from: {DATA_FILE}")
df = pd.read_parquet(DATA_FILE).tail(1000)

# Mapeo de columnas si vienen en formato corto (t, o, h, l, c, v)
column_map = {
    't': 'timestamp',
    'o': 'open',
    'h': 'high',
    'l': 'low',
    'c': 'close',
    'v': 'volume'
}
if 'c' in df.columns and 'close' not in df.columns:
    df = df.rename(columns=column_map)

# Asegurar que las columnas sean numéricas y timestamp sea datetime
for col in ['open', 'high', 'low', 'close', 'volume']:
    df[col] = pd.to_numeric(df[col])
if 'timestamp' in df.columns:
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s' if df['timestamp'].iloc[0] > 1e10 else None)

df_copy = df.copy()
threshold = 2.0
lookback_structure = 15

df_copy['body_size'] = abs(df_copy['close'] - df_copy['open'])
df_copy['total_size'] = df_copy['high'] - df_copy['low']
df_copy['avg_body'] = df_copy['body_size'].rolling(window=20).mean()
df_copy['avg_total'] = df_copy['total_size'].rolling(window=20).mean()

df_copy['is_imbalance'] = (df_copy['body_size'] > (df_copy['avg_body'] * threshold)) & (df_copy['total_size'] > df_copy['avg_total'])
df_copy['imbalance_bullish'] = df_copy['is_imbalance'] & (df_copy['close'] > df_copy['open'])
df_copy['imbalance_bearish'] = df_copy['is_imbalance'] & (df_copy['close'] < df_copy['open'])

df_copy['struct_high'] = df_copy['high'].shift(1).rolling(window=lookback_structure).max()
df_copy['struct_low'] = df_copy['low'].shift(1).rolling(window=lookback_structure).min()

bullish_sweep = df_copy['low'].shift(1) <= df_copy['struct_low'].shift(1)
bullish_bos = df_copy['close'] > df_copy['struct_high']

base_fvg_bullish = (df_copy['low'] > df_copy['high'].shift(2)) & df_copy['imbalance_bullish'].shift(1)

print(f"Total rows: {len(df_copy)}")
print(f"Base Bull FVGs: {base_fvg_bullish.sum()}")
print(f"High-Prob Bull FVGs: {(base_fvg_bullish & (bullish_sweep.shift(1) | bullish_bos.shift(1))).sum()}")

# Validar que los indicadores SMC devuelvan algo
# identify_order_blocks devuelve un DataFrame con columnas 'ob_bullish' y 'ob_bearish'
df_analyzed = identify_order_blocks(df)
print(f"Order Blocks identified: Bull={df_analyzed['ob_bullish'].sum()} Bear={df_analyzed['ob_bearish'].sum()}")

# Validar extract_smc_coordinates (este sí devuelve un dict)
coords = extract_smc_coordinates(df_analyzed)
print(f"Active OBs in coordinates: Bull={len(coords['order_blocks']['bullish'])} Bear={len(coords['order_blocks']['bearish'])}")
