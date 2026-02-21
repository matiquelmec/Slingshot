import numpy as np

def detect_liquidity_clusters(bids: list, asks: list, top_n: int = 3) -> dict:
    """
    Recibe el Order Book Nivel 2 crudo de Binance (bids y asks).
    Filtra y agrupa (clusteriza) la liquidez para encontrar verdaderos "Muros" institucionales.
    Retorna los Top N clusters de compras y ventas más masivos.
    
    Un bid/ask en Binance L2 viene como [precio_str, cantidad_str].
    """
    if not bids or not asks:
        return {"bids": [], "asks": []}
        
    try:
        # 1. Convertir a float
        bids_float = [[float(p), float(q)] for p, q in bids]
        asks_float = [[float(p), float(q)] for p, q in asks]
        
        # 2. Ordenar por cantidad (volumen de la orden) de mayor a menor
        bids_sorted = sorted(bids_float, key=lambda x: x[1], reverse=True)
        asks_sorted = sorted(asks_float, key=lambda x: x[1], reverse=True)
        
        # 3. Extraer el "Top N" de verdaderos muros de liquidez
        top_bids = bids_sorted[:top_n]
        top_asks = asks_sorted[:top_n]
        
        # 4. Formatear para el Frontend
        # Retornamos dicts listos para inyectar en el `neural_pulse`
        
        formatted_bids = [{"price": b[0], "volume": b[1]} for b in top_bids if b[1] > 0]
        formatted_asks = [{"price": a[0], "volume": a[1]} for a in top_asks if a[1] > 0]
        
        return {
            "bids": formatted_bids,  # Zonas Verdes Fuertes
            "asks": formatted_asks   # Zonas Rojas Fuertes
        }
        
    except Exception as e:
        print(f"[Liquidity Engine] Error al procesar Order Book: {e}")
        return {"bids": [], "asks": []}
