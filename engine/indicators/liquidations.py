import pandas as pd
import numpy as np
from typing import List, Dict, Any

def estimate_liquidation_clusters(df: pd.DataFrame, current_price: float) -> List[Dict[str, Any]]:
    """
    Motor Táctico de Estimación de Liquidaciones (Estilo Hyblock).
    Detecta zonas donde el apalancamiento masivo (100x, 50x, 25x) entraría en liquidación.
    """
    if df.empty or current_price is None:
        return []

    clusters = []
    
    # Leverages comunes y su margen de seguridad
    # 100x -> 1% de movimiento
    # 50x  -> 2%
    # 25x  -> 4%
    leverages = [
        {"lev": 100, "margin": 0.01},
        {"lev": 50,  "margin": 0.02},
        {"lev": 25,  "margin": 0.04}
    ]

    # Encontrar Pivots (Swing Highs y Lows) en las últimas 100 velas
    lookback = min(len(df), 100)
    recent_df = df.iloc[-lookback:]
    
    # Detección simple de pivotes locales
    for i in range(2, len(recent_df) - 2):
        high_pivot = (recent_df['high'].iloc[i] > recent_df['high'].iloc[i-1] and 
                      recent_df['high'].iloc[i] > recent_df['high'].iloc[i-2] and 
                      recent_df['high'].iloc[i] > recent_df['high'].iloc[i+1] and 
                      recent_df['high'].iloc[i] > recent_df['high'].iloc[i+2])
        
        low_pivot = (recent_df['low'].iloc[i] < recent_df['low'].iloc[i-1] and 
                     recent_df['low'].iloc[i] < recent_df['low'].iloc[i-2] and 
                     recent_df['low'].iloc[i] < recent_df['low'].iloc[i+1] and 
                     recent_df['low'].iloc[i] < recent_df['low'].iloc[i+2])

        if high_pivot:
            pivot_price = recent_df['high'].iloc[i]
            # Si hay un techo, los SHORTS ponen sus stops arriba. 
            # Si el precio sube, sus liquidaciones están arriba del pivot.
            for config in leverages:
                liq_price = pivot_price * (1 + config['margin'] + 0.001) # +0.1% spread safe
                if liq_price > current_price:
                    clusters.append({
                        "price": liq_price,
                        "volume": config['lev'] * 1000, # Volumen sintético basado en lev
                        "type": "SHORT_LIQ",
                        "leverage": config['lev']
                    })

        if low_pivot:
            pivot_price = recent_df['low'].iloc[i]
            # Si hay un piso, los LONGS ponen sus stops abajo.
            for config in leverages:
                liq_price = pivot_price * (1 - config['margin'] - 0.001)
                if liq_price < current_price:
                    clusters.append({
                        "price": liq_price,
                        "volume": config['lev'] * 1000,
                        "type": "LONG_LIQ",
                        "leverage": config['lev']
                    })

    # Agrupar clusters cercanos (Bucketization)
    if not clusters:
        return []

    # Ordenar por precio
    clusters.sort(key=lambda x: x['price'])
    
    merged = []
    if clusters:
        # Usamos un bucket del 0.15% del precio actual
        bucket_size = current_price * 0.0015
        
        current_group = clusters[0]
        for next_cluster in clusters[1:]:
            if abs(next_cluster['price'] - current_group['price']) <= bucket_size and next_cluster['type'] == current_group['type']:
                # Combinar
                old_vol = current_group['volume']
                new_vol = next_cluster['volume']
                # Weighted average price
                current_group['price'] = (current_group['price'] * old_vol + next_cluster['price'] * new_vol) / (old_vol + new_vol)
                current_group['volume'] += new_vol
                current_group['leverage'] = max(current_group['leverage'], next_cluster['leverage'])
            else:
                merged.append(current_group)
                current_group = next_cluster
        merged.append(current_group)

    # Normalizar "Strength" (0-100)
    if merged:
        max_vol = max(c['volume'] for c in merged)
        for c in merged:
            c['strength'] = int((c['volume'] / max_vol) * 100)
            # Limpiar para JSON
            c['price'] = round(c['price'], 8 if current_price < 1 else 2)

    # Devolver los 10 más relevantes (5 arriba, 5 abajo)
    shorts = sorted([c for c in merged if c['type'] == "SHORT_LIQ"], key=lambda x: x['price'])[:5]
    longs = sorted([c for c in merged if c['type'] == "LONG_LIQ"], key=lambda x: x['price'], reverse=True)[:5]
    
    return longs + shorts
