import pandas as pd
import numpy as np
from pathlib import Path
from scipy.signal import find_peaks

def identify_order_blocks(df: pd.DataFrame, threshold: float = 2.0) -> pd.DataFrame:
    """
    SMC Nivel 2: Detecta Order Blocks e Imbalances (Fair Value Gaps).
    Actualizado: Umbral más alto y filtro de tamaño mínimo para evitar ruido.
    """
    df = df.copy()
    
    # 1. Calcular tamaño y cuerpo de las velas
    df['body_size'] = abs(df['close'] - df['open'])
    df['total_size'] = df['high'] - df['low']
    df['avg_body'] = df['body_size'].rolling(window=20).mean()
    df['avg_total'] = df['total_size'].rolling(window=20).mean()
    
    # 2. Identificar Velas Institucionales (Expansión Fuerte / Imbalance)
    # Exigimos cuerpo grande (threshold relativo) Y que el tamaño total sea mayor al promedio (filtra dojis anchos)
    df['is_imbalance'] = (df['body_size'] > (df['avg_body'] * threshold)) & (df['total_size'] > df['avg_total'])
    
    # Dirección del imbalance
    df['imbalance_bullish'] = df['is_imbalance'] & (df['close'] > df['open'])
    df['imbalance_bearish'] = df['is_imbalance'] & (df['close'] < df['open'])
    
    # 3. Detectar Order Blocks (OB)
    # Inicializamos columnas
    df['ob_bullish'] = False
    df['ob_bearish'] = False
    
    # Bullish OB: La vela actual es alcista fuerte, la vela ANTERIOR fue bajista
    prev_bearish = df['close'].shift(1) < df['open'].shift(1)
    mask_bull_ob = df['imbalance_bullish'] & prev_bearish
    df.loc[mask_bull_ob, 'ob_bullish'] = True 
    
    # Bearish OB: La vela actual es bajista fuerte, la vela ANTERIOR fue alcista
    prev_bullish = df['close'].shift(1) > df['open'].shift(1)
    mask_bear_ob = df['imbalance_bearish'] & prev_bullish
    df.loc[mask_bear_ob, 'ob_bearish'] = True
    
    # 4. Fair Value Gaps (FVG) Básicos Filtrados por Imbalance
    # FVG Alcista: Low(3) > High(1) Y Imbalance(2) Alcista
    df['fvg_bullish'] = (df['low'] > df['high'].shift(2)) & df['imbalance_bullish'].shift(1)
    
    # FVG Bajista: High(3) < Low(1) Y Imbalance(2) Bajista
    df['fvg_bearish'] = (df['high'] < df['low'].shift(2)) & df['imbalance_bearish'].shift(1)
    
    return df

def identify_support_resistance(df: pd.DataFrame, window: int = 21, num_levels: int = 5) -> pd.DataFrame:
    """
    Identifica Soportes y Resistencias Horizontales (Topografía de Mercado).
    Utiliza detección algorítmica de picos (Local Maxima y Minima) y los agrupa en niveles de precio.
    """
    df = df.copy()
    
    # Si tenemos muy pocos datos, retornamos sin calcular
    if len(df) < window * 2:
        df['nearest_support'] = np.nan
        df['nearest_resistance'] = np.nan
        return df

    # 1. Encontrar Pivot Highs (Resistencias) y Pivot Lows (Soportes)
    # window determina cuán "lejos" deben estar los picos para ser relevantes
    
    # Encontrar índices de los máximos locales
    highs = df['high'].values
    peak_indices, _ = find_peaks(highs, distance=window)
    resistance_prices = highs[peak_indices]
    
    # Encontrar índices de los mínimos locales (invirtiendo la serie)
    lows = -df['low'].values
    valley_indices, _ = find_peaks(lows, distance=window)
    support_prices = -lows[valley_indices] # Restauramos valores positivos
    
    # Inicializamos columnas para el soporte y resistencia INMEDIATO más cercano al precio actual
    df['resistance_level'] = np.nan
    df['support_level'] = np.nan
    
    # Nota: Analizar iterativamente cada vela es lento para Big Data, por lo que este método 
    # asume un cálculo de los S/R relevantes HASTA la vela actual.
    
    for i in range(window * 2, len(df)):
        current_price = df['close'].iloc[i]
        
        # Filtrar picos que ocurrieron ANTES de la vela actual para evitar "mirar al futuro"
        valid_res_indices = [idx for idx in peak_indices if idx < i]
        valid_sup_indices = [idx for idx in valley_indices if idx < i]
        
        if valid_res_indices and valid_sup_indices:
            # Seleccionar los precios de esos picos válidos
            valid_res_prices = highs[valid_res_indices]
            valid_sup_prices = df['low'].values[valid_sup_indices]
            
            # Resistencia Inmediata: El pico histórico más cercano que está POR ENCIMA del precio actual
            res_above = [r for r in valid_res_prices if r > current_price]
            nearest_res = min(res_above) if res_above else np.nan
            
            # Soporte Inmediato: El valle histórico más cercano que está POR DEBAJO del precio actual
            sup_below = [s for s in valid_sup_prices if s < current_price]
            nearest_sup = max(sup_below) if sup_below else np.nan
            
            df.loc[df.index[i], 'resistance_level'] = nearest_res
            df.loc[df.index[i], 'support_level'] = nearest_sup
    
    # Rellenar (forward fill) para mantener el nivel hasta que se detecte uno nuevo o se rompa
    df['resistance_level'] = df['resistance_level'].ffill()
    df['support_level'] = df['support_level'].ffill()
    
    return df

def extract_smc_coordinates(df: pd.DataFrame) -> dict:
    """
    Algoritmo de Mitigación Vectorizado:
    Recorre el DataFrame secuencialmente para rastrear el ciclo de vida de OBs y FVGs.
    Retorna ÚNICAMENTE las zonas que siguen "vivas" (sin mitigar) al final del periodo.
    """
    active_bullish_obs = []
    active_bearish_obs = []
    active_bullish_fvgs = []
    active_bearish_fvgs = []
    
    # Iteramos sobre el DataFrame para rastrear mitigaciones paso a paso
    for i, row in df.iterrows():
        loc = df.index.get_loc(i)
        current_low = row['low']
        current_high = row['high']
        current_ts = row['timestamp'].timestamp()
        
        # --- 1. PROCESAR MITIGACIONES DE ZONAS EXISTENTES ---
        
        # Mitigación FVG Alcista: Para mantener el gráfico extremadamente limpio y preciso,
        # si el precio cruza más del 50% del gap, lo damos por mitigado y destruido.
        active_bullish_fvgs = [fvg for fvg in active_bullish_fvgs if current_low > (fvg['bottom'] + (fvg['top'] - fvg['bottom']) * 0.5)]
        
        # Mitigación FVG Bajista: Si el precio sube por encima del 50% del gap, se mitiga.
        active_bearish_fvgs = [fvg for fvg in active_bearish_fvgs if current_high < (fvg['bottom'] + (fvg['top'] - fvg['bottom']) * 0.5)]
        
        # Mitigación OB Alcista: Stop loss tocado o bloque mitigado en un 50% (para limpieza de gráfico)
        active_bullish_obs = [ob for ob in active_bullish_obs if current_low > (ob['bottom'] + (ob['top'] - ob['bottom']) * 0.5)]
        
        # Mitigación OB Bajista: Stop loss tocado o bloque mitigado en un 50%
        active_bearish_obs = [ob for ob in active_bearish_obs if current_high < (ob['bottom'] + (ob['top'] - ob['bottom']) * 0.5)]
        
        
        # --- 2. REGISTRAR NUEVAS ZONAS ---
        
        # (A) Nuevos Order Blocks
        if row.get('ob_bullish') == True and loc > 0:
            ob_candle = df.iloc[loc - 1]
            active_bullish_obs.append({
                "time": ob_candle['timestamp'].timestamp(),
                "top": float(ob_candle['high']),
                "bottom": float(ob_candle['low']),
                "status": "active",
                "confirmation_time": current_ts
            })
            
        if row.get('ob_bearish') == True and loc > 0:
            ob_candle = df.iloc[loc - 1]
            active_bearish_obs.append({
                "time": ob_candle['timestamp'].timestamp(),
                "top": float(ob_candle['high']),
                "bottom": float(ob_candle['low']),
                "status": "active",
                "confirmation_time": current_ts
            })
            
        # (B) Nuevos Fair Value Gaps (Requieren 3 velas: C1, C2_imbalance, C3_actual)
        if row.get('fvg_bullish') == True and loc >= 2:
            c1 = df.iloc[loc - 2]
            # Techo del gap = Piso de C3 (actual), Piso del gap = Techo de C1
            top = float(row['low'])
            bottom = float(c1['high'])
            if top > bottom: # Check de seguridad
                active_bullish_fvgs.append({
                    "time": c1['timestamp'].timestamp(),
                    "top": top,
                    "bottom": bottom,
                    "status": "active",
                    "confirmation_time": current_ts
                })
                
        if row.get('fvg_bearish') == True and loc >= 2:
            c1 = df.iloc[loc - 2]
            # Techo del gap = Piso de C1, Piso del gap = Techo de C3 (actual)
            top = float(c1['low'])
            bottom = float(row['high'])
            if top > bottom: # Check de seguridad
                active_bearish_fvgs.append({
                    "time": c1['timestamp'].timestamp(),
                    "top": top,
                    "bottom": bottom,
                    "status": "active",
                    "confirmation_time": current_ts
                })
                
    return {
        "order_blocks": {
            "bullish": active_bullish_obs,
            "bearish": active_bearish_obs
        },
        "fvgs": {
            "bullish": active_bullish_fvgs,
            "bearish": active_bearish_fvgs
        }
    }

if __name__ == "__main__":
    file_path = Path(__file__).parent.parent.parent / "data" / "btcusdt_15m.parquet"
    if file_path.exists():
        data = pd.read_parquet(file_path).tail(200) # Probemos en las últimas 200 velas
        analyzed_data = identify_order_blocks(data)
        
        # Test Support and Resistance
        analyzed_data = identify_support_resistance(analyzed_data)
        
        coords = extract_smc_coordinates(analyzed_data)
        
        print(f"Bullish Order Blocks Escaneados: {len(coords['order_blocks']['bullish'])}")
        print(f"Bearish Order Blocks Escaneados: {len(coords['order_blocks']['bearish'])}")
        
        if coords['order_blocks']['bullish']:
            latest_bull = coords['order_blocks']['bullish'][-1]
            print(f"Último Bull OB: \n{latest_bull}")
            
    else:
        print("Data file not found.")
