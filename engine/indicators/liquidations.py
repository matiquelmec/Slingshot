import pandas as pd
import numpy as np
from typing import List, Dict, Any

def estimate_liquidation_clusters(df: pd.DataFrame, current_price: float) -> List[Dict[str, Any]]:
    """
    Motor Táctico de Estimación de Liquidaciones v2.0 (Volume-Weighted Edition).
    Detecta zonas donde el apalancamiento masivo entraría en liquidación,
    ponderando la fuerza del cluster por el volumen negociado en el pivot.
    """
    if df.empty or current_price is None:
        return []

    clusters = []
    
    # Leverages comunes y su margen de seguridad
    leverages = [
        {"lev": 100, "margin": 0.01},
        {"lev": 50,  "margin": 0.02},
        {"lev": 25,  "margin": 0.04}
    ]

    # Encontrar Pivots (Swing Highs y Lows) en las últimas 100 velas
    lookback = min(len(df), 100)
    recent_df = df.iloc[-lookback:]
    
    # Media de volumen para normalización
    avg_vol = recent_df['volume'].mean() if 'volume' in recent_df.columns else 1.0

    # Detección de pivotes locales
    for i in range(2, len(recent_df) - 2):
        # ... lógica de pivots ...
        high_pivot = (recent_df['high'].iloc[i] > recent_df['high'].iloc[i-1] and 
                      recent_df['high'].iloc[i] > recent_df['high'].iloc[i-2] and 
                      recent_df['high'].iloc[i] > recent_df['high'].iloc[i+1] and 
                      recent_df['high'].iloc[i] > recent_df['high'].iloc[i+2])
        
        low_pivot = (recent_df['low'].iloc[i] < recent_df['low'].iloc[i-1] and 
                     recent_df['low'].iloc[i] < recent_df['low'].iloc[i-2] and 
                     recent_df['low'].iloc[i] < recent_df['low'].iloc[i+1] and 
                     recent_df['low'].iloc[i] < recent_df['low'].iloc[i+2])

        # Volumen negociado en este pivot (factor de intensidad institucional)
        pivot_vol = recent_df['volume'].iloc[i] if 'volume' in recent_df.columns else avg_vol
        vol_multiplier = max(1.0, pivot_vol / avg_vol) if avg_vol > 0 else 1.0

        if high_pivot:
            pivot_price = recent_df['high'].iloc[i]
            for config in leverages:
                liq_price = pivot_price * (1 + config['margin'] + 0.001)
                if liq_price > current_price:
                    clusters.append({
                        "price": liq_price,
                        "volume": config['lev'] * 1000 * vol_multiplier, # Ponderado por volumen real
                        "type": "SHORT_LIQ",
                        "leverage": config['lev'],
                        "base_vol": pivot_vol
                    })

        if low_pivot:
            pivot_price = recent_df['low'].iloc[i]
            for config in leverages:
                liq_price = pivot_price * (1 - config['margin'] - 0.001)
                if liq_price < current_price:
                    clusters.append({
                        "price": liq_price,
                        "volume": config['lev'] * 1000 * vol_multiplier,
                        "type": "LONG_LIQ",
                        "leverage": config['lev'],
                        "base_vol": pivot_vol
                    })

    if not clusters:
        return []

    # Bucketization (0.15% range)
    clusters.sort(key=lambda x: x['price'])
    merged = []
    bucket_size = current_price * 0.0015
    
    current_group = clusters[0]
    for next_cluster in clusters[1:]:
        if abs(next_cluster['price'] - current_group['price']) <= bucket_size and next_cluster['type'] == current_group['type']:
            old_vol = current_group['volume']
            new_vol = next_cluster['volume']
            current_group['price'] = (current_group['price'] * old_vol + next_cluster['price'] * new_vol) / (old_vol + new_vol)
            current_group['volume'] += new_vol
            current_group['leverage'] = max(current_group['leverage'], next_cluster['leverage'])
        else:
            merged.append(current_group)
            current_group = next_cluster
    merged.append(current_group)

    # Normalización Final
    if merged:
        max_vol = max(c['volume'] for c in merged)
        for c in merged:
            c['strength'] = int((c['volume'] / max_vol) * 100)
            c['price'] = round(c['price'], 8 if current_price < 1 else 2)

    # Top 10 (5 arriba, 5 abajo)
    shorts = sorted([c for c in merged if c['type'] == "SHORT_LIQ"], key=lambda x: x['price'])[:5]
    longs = sorted([c for c in merged if c['type'] == "LONG_LIQ"], key=lambda x: x['price'], reverse=True)[:5]
    
    return longs + shorts
