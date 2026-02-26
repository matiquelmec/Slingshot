import pandas as pd
from engine.indicators.structure import identify_order_blocks, extract_smc_coordinates

df = pd.read_parquet('data/btcusdt_15m.parquet').tail(1000)

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
print(f"High-Prob Bull FVGs: (base_fvg_bullish & (bullish_sweep.shift(1) | bullish_bos.shift(1))).sum() = {(base_fvg_bullish & (bullish_sweep.shift(1) | bullish_bos.shift(1))).sum()}")
