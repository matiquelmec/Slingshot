from engine.core.logger import logger
import numpy as np
import time
from typing import List, Dict, Any, Optional

def analyze_neural_heatmap(bids: list, asks: list, current_price: float) -> dict:
    """
    Motor Neural de Liquidez v5.7.
    Procesa el Order Book profundo (L2) para generar un mapa de calor institucional.
    
    Analiza:
    1. Desequilibrio de Profundidad (Buy/Sell Pressure).
    2. Niveles "Imán" (Clusters masivos de liquidez).
    3. Gradiente de Calor (Proximidad vs Volumen).
    """
    if not bids or not asks:
        return {"bids": [], "asks": [], "imbalance": 0.0, "status": "CALIBRATING"}
        
    try:
        # 1. Normalización y Limpieza
        b_prices = np.array([float(b[0]) for b in bids])
        b_vols   = np.array([float(b[1]) for b in bids])
        a_prices = np.array([float(a[0]) for a in asks])
        a_vols   = np.array([float(a[1]) for a in asks])

        total_bids_vol = np.sum(b_vols)
        total_asks_vol = np.sum(a_vols)
        
        # 2. Cálculo de Desequilibrio (Imbalance)
        # -1.0 (Ventas Masivas) a +1.0 (Compras Masivas)
        imbalance = (total_bids_vol - total_asks_vol) / (total_bids_vol + total_asks_vol) if (total_bids_vol + total_asks_vol) > 0 else 0.0

        # 3. Identificación de Niveles "Elite" (Muros Institucionales)
        # Filtramos niveles que tengan al menos 2 desvíos estándar más que la media del book
        mean_vol = (np.mean(b_vols) + np.mean(a_vols)) / 2
        std_vol  = (np.std(b_vols) + np.std(a_vols)) / 2
        threshold = mean_vol + (std_vol * 1.5)

        def _get_hot_levels(prices, vols, is_bid: bool) -> List[Dict[str, Any]]:
            levels = []
            for p, v in zip(prices, vols):
                if v >= threshold:
                    # Cálculo de Calor (0-100)
                    # Basado en Volumen relativo y Proximidad (a mayor cercanía, más 'calor')
                    rel_vol = v / np.max(vols) if np.max(vols) > 0 else 1.0
                    dist_pct = abs(p - current_price) / current_price
                    # Inversamente proporcional a la distancia (max 2%)
                    proximity = max(0, 1 - (dist_pct / 0.02)) 
                    
                    heat_score = int(((rel_vol * 0.7) + (proximity * 0.3)) * 100)
                    
                    levels.append({
                        "price": round(p, 2 if current_price > 10 else 4),
                        "volume": round(v, 4),
                        "heat": min(100, heat_score),
                        "type": "SUPPORT" if is_bid else "RESISTANCE"
                    })
            return sorted(levels, key=lambda x: x["heat"], reverse=True)[:5]

        hot_bids = _get_hot_levels(b_prices, b_vols, True)
        hot_asks = _get_hot_levels(a_prices, a_vols, False)

        return {
            "imbalance": round(imbalance, 4),
            "total_bids": round(total_bids_vol, 2),
            "total_asks": round(total_asks_vol, 2),
            "hot_bids": hot_bids,
            "hot_asks": hot_asks,
            "bids": hot_bids, # Aliases de compatibilidad v5.7.15
            "asks": hot_asks, # Aliases de compatibilidad v5.7.15
            "sentiment": "BULLISH" if imbalance > 0.15 else "BEARISH" if imbalance < -0.15 else "NEUTRAL",
            "timestamp": time.time() if 'time' in globals() else 0
        }
        
    except Exception as e:
        logger.error(f"[Neural Heatmap] Engine Error: {e}")
        return {"imbalance": 0.0, "status": "ERROR"}

def detect_liquidity_clusters(bids: list, asks: list, top_n: int = 3) -> dict:
    """Legacy v4.0 Filter (mantiene compatibilidad con el router actual)."""
    if not bids or not asks: return {"bids": [], "asks": []}
    try:
        bids_sorted = sorted([[float(p), float(q)] for p, q in bids], key=lambda x: x[1], reverse=True)
        asks_sorted = sorted([[float(p), float(q)] for p, q in asks], key=lambda x: x[1], reverse=True)
        return {
            "bids": [{"price": b[0], "volume": b[1]} for b in bids_sorted[:top_n] if b[1] > 0],
            "asks": [{"price": a[0], "volume": a[1]} for a in asks_sorted[:top_n] if a[1] > 0]
        }
    except: return {"bids": [], "asks": []}
