import pandas as pd
import numpy as np
from pathlib import Path
from scipy.signal import find_peaks

def identify_order_blocks(df: pd.DataFrame, threshold: float = 1.5) -> pd.DataFrame:
    """
    SMC Nivel 2: Detecta Order Blocks e Imbalances (Fair Value Gaps).
    """
    df = df.copy()
    
    # 1. Calcular tamaño y cuerpo de las velas
    df['body_size'] = abs(df['close'] - df['open'])
    df['total_size'] = df['high'] - df['low']
    df['avg_body'] = df['body_size'].rolling(window=20).mean()
    
    # 2. Identificar Velas Institucionales (Expansión Fuerte / Imbalance)
    # Una vela es institucional si su cuerpo es bastante más grande que el promedio reciente (ej. 1.5x)
    df['is_imbalance'] = df['body_size'] > (df['avg_body'] * threshold)
    
    # Dirección del imbalance
    df['imbalance_bullish'] = df['is_imbalance'] & (df['close'] > df['open'])
    df['imbalance_bearish'] = df['is_imbalance'] & (df['close'] < df['open'])
    
    # 3. Detectar Order Blocks (OB)
    # Un Bullish OB es la ÚLTIMA VELA BAJISTA antes de un movimiento alcista fuerte (Imbalance Bullish)
    # Buscamos si la vela ACTUAL es un imbalance alcista, y si la ANTERIOR fue bajista, marcamos la anterior como OB.
    
    # Inicializamos columnas
    df['ob_bullish'] = False
    df['ob_bearish'] = False
    
    # Bullish OB: La vela actual es alcista fuerte, la vela ANTERIOR fue bajista
    prev_bearish = df['close'].shift(1) < df['open'].shift(1)
    mask_bull_ob = df['imbalance_bullish'] & prev_bearish
    # Marcamos la vela actual como confirmación del OB que se formó en la vela anterior
    # (En la práctica de backtesting, usamos la vela de confirmación para saber que el OB existe)
    df.loc[mask_bull_ob, 'ob_bullish'] = True 
    
    # Bearish OB: La vela actual es bajista fuerte, la vela ANTERIOR fue alcista
    prev_bullish = df['close'].shift(1) > df['open'].shift(1)
    mask_bear_ob = df['imbalance_bearish'] & prev_bullish
    df.loc[mask_bear_ob, 'ob_bearish'] = True
    
    # 4. Fair Value Gaps (FVG) Básicos Filtrados por Imbalance
    # FVG Alcista: El Low de la vela actual no toca el High de hace 2 velas, Y la vela anterior (centro) fue un imbalance alcista
    df['fvg_bullish'] = (df['low'] > df['high'].shift(2)) & df['imbalance_bullish'].shift(1)
    
    # FVG Bajista: El High de la vela actual no toca el Low de hace 2 velas, Y la vela anterior (centro) fue un imbalance bajista
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
    Toma el DataFrame con las columnas calculadas de SMC 
    (ob_bullish, ob_bearish, fvg_bullish, fvg_bearish) y extrae las coordenadas reales.
    Retorna un diccionario con listas de objetos listos para la UI.
    """
    # Necesitamos las velas con sus indices temporales
    bullish_obs = []
    bearish_obs = []
    bullish_fvgs = []
    bearish_fvgs = []
    
    # ── 1. Extraer Order Blocks (OB) ──
    bull_confirmations = df[df['ob_bullish'] == True]
    for idx_conf in bull_confirmations.index:
        loc_conf = df.index.get_loc(idx_conf)
        if loc_conf > 0:
            ob_candle = df.iloc[loc_conf - 1] 
            conf_candle = df.iloc[loc_conf]
            
            bullish_obs.append({
                "time": ob_candle['timestamp'].timestamp(),
                "top": float(ob_candle['high']),
                "bottom": float(ob_candle['low']),
                "status": "active",
                "confirmation_time": conf_candle['timestamp'].timestamp()
            })

    bear_confirmations = df[df['ob_bearish'] == True]
    for idx_conf in bear_confirmations.index:
        loc_conf = df.index.get_loc(idx_conf)
        if loc_conf > 0:
            ob_candle = df.iloc[loc_conf - 1] 
            conf_candle = df.iloc[loc_conf]
            
            bearish_obs.append({
                "time": ob_candle['timestamp'].timestamp(),
                "top": float(ob_candle['high']),
                "bottom": float(ob_candle['low']),
                "status": "active",
                "confirmation_time": conf_candle['timestamp'].timestamp()
            })
            
    # ── 2. Extraer Fair Value Gaps (FVG) ──
    # Bullish FVG (Demand): Gap entre el High de la Vela 1 (C(-2)) y el Low de la Vela 3 (C)
    bull_fvg_confs = df[df['fvg_bullish'] == True]
    for idx_conf in bull_fvg_confs.index:
        loc_conf = df.index.get_loc(idx_conf)
        if loc_conf >= 2:
            c1 = df.iloc[loc_conf - 2]
            c3 = df.iloc[loc_conf]
            
            bullish_fvgs.append({
                "time": c1['timestamp'].timestamp(),
                "top": float(c3['low']),      # El techo del gap es el bottom de C3
                "bottom": float(c1['high']),   # El piso del gap es el top de C1
                "status": "active",
                "confirmation_time": c3['timestamp'].timestamp()
            })

    # Bearish FVG (Supply): Gap entre el Low de la Vela 1 (C(-2)) y el High de la Vela 3 (C)
    bear_fvg_confs = df[df['fvg_bearish'] == True]
    for idx_conf in bear_fvg_confs.index:
        loc_conf = df.index.get_loc(idx_conf)
        if loc_conf >= 2:
            c1 = df.iloc[loc_conf - 2]
            c3 = df.iloc[loc_conf]
            
            bearish_fvgs.append({
                "time": c1['timestamp'].timestamp(),
                "top": float(c1['low']),       # El techo del gap es el piso de C1
                "bottom": float(c3['high']),   # el piso del gap es el techo de C3
                "status": "active",
                "confirmation_time": c3['timestamp'].timestamp()
            })
            
    return {
        "order_blocks": {
            "bullish": bullish_obs,
            "bearish": bearish_obs
        },
        "fvgs": {
            "bullish": bullish_fvgs,
            "bearish": bearish_fvgs
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
