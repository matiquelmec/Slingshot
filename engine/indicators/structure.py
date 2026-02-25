import pandas as pd
import numpy as np
from pathlib import Path
from scipy.signal import find_peaks

# Fase 1: Window óptimo por temporalidad
# Principio: ventana = cantidad de velas que forman una "estructura" significativa en esa TF
WINDOW_BY_INTERVAL: dict[str, int] = {
    '1m':  5,   # 5 min de estructura mínima
    '3m':  7,
    '5m':  10,
    '15m': 21,  # ~5 horas de estructura
    '30m': 18,
    '1h':  21,  # ~21 horas
    '2h':  15,
    '4h':  14,  # ~56 horas = ~2.3 días
    '6h':  10,
    '8h':  10,
    '12h': 8,
    '1d':  8,   # 8 días de estructura
    '3d':  5,
    '1w':  4,
}

def identify_order_blocks(df: pd.DataFrame, threshold: float = 2.0, lookback_structure: int = 15) -> pd.DataFrame:
    """
    SMC Nivel 3 (God Mode): Detecta Order Blocks e Imbalances (Fair Value Gaps).
    Filtra los High-Probability OBs exigiendo Liquidity Sweep o Break of Structure.
    """
    df = df.copy()
    
    # 1. Calcular tamaño y cuerpo de las velas
    df['body_size'] = abs(df['close'] - df['open'])
    df['total_size'] = df['high'] - df['low']
    df['avg_body'] = df['body_size'].rolling(window=20).mean()
    df['avg_total'] = df['total_size'].rolling(window=20).mean()
    
    # 2. Identificar Velas Institucionales (Expansión Fuerte / Imbalance)
    df['is_imbalance'] = (df['body_size'] > (df['avg_body'] * threshold)) & (df['total_size'] > df['avg_total'])
    
    df['imbalance_bullish'] = df['is_imbalance'] & (df['close'] > df['open'])
    df['imbalance_bearish'] = df['is_imbalance'] & (df['close'] < df['open'])
    
    # 3. Mapeo de Estructura Institucional (Vectorizado)
    # Rastrear el techo y piso reciente para ver si el OB causa ruptura o barrido
    # Usamos shift(1) para no incluir la vela actual en el lookback
    df['struct_high'] = df['high'].shift(1).rolling(window=lookback_structure).max()
    df['struct_low'] = df['low'].shift(1).rolling(window=lookback_structure).min()
    
    # 4. Detectar Order Blocks (OB) Base (Inducements potenciales)
    prev_bearish = df['close'].shift(1) < df['open'].shift(1)
    base_bull_ob = df['imbalance_bullish'] & prev_bearish
    
    prev_bullish = df['close'].shift(1) > df['open'].shift(1)
    base_bear_ob = df['imbalance_bearish'] & prev_bullish
    
    # 5. Filtrado "SMC God Mode" (High-Probability)
    # Regla OB Alcista HP:
    # A) La vela roja previa (el bloque) barrió el mínimo estructural (Liquidity Sweep) -> shift(1)['low'] < struct_low
    # B) O la vela verde de expansión rompió un techo estructural importante (BOS) -> ['close'] > struct_high
    
    bullish_sweep = df['low'].shift(1) <= df['struct_low'].shift(1)
    bullish_bos = df['close'] > df['struct_high']
    
    bearish_sweep = df['high'].shift(1) >= df['struct_high'].shift(1)
    bearish_bos = df['close'] < df['struct_low']
    
    # Solo es OB válido si tiene Imbalance + Reversion + (Sweep o BOS)
    df['ob_bullish'] = base_bull_ob & (bullish_sweep | bullish_bos)
    df['ob_bearish'] = base_bear_ob & (bearish_sweep | bearish_bos)
    
    # 6. Fair Value Gaps (FVG) Filrados SMC God Mode (High-Probability)
    df['fvg_bullish'] = (df['low'] > df['high'].shift(2)) & df['imbalance_bullish'].shift(1)
    df['fvg_bearish'] = (df['high'] < df['low'].shift(2)) & df['imbalance_bearish'].shift(1)
    
    return df

def identify_support_resistance(
    df: pd.DataFrame,
    window: int = 21,
    num_levels: int = 5,
    interval: str = '15m',
) -> pd.DataFrame:
    """
    S/R Profesional v3 — Multi-Timeframe ready.

    Mejoras sobre v2:
    - Fase 1: Window dinámico por temporalidad (WINDOW_BY_INTERVAL)
    - Fase 3: Volume score en cada cluster (volumen ponderado por toque)
    """
    df = df.copy()

    # Fase 1: usar window dinámico si no se override explícitamente
    window = WINDOW_BY_INTERVAL.get(interval, window)

    if len(df) < window * 2:
        df['support_level']    = np.nan
        df['resistance_level'] = np.nan
        return df

    highs  = df['high'].values
    lows   = df['low'].values
    closes = df['close'].values

    # ── 1. ATR dinámico para tolerancia y umbral de invalidación ─────────────
    tr = np.maximum(
        highs - lows,
        np.maximum(
            np.abs(highs - np.roll(closes, 1)),
            np.abs(lows  - np.roll(closes, 1))
        )
    )
    tr[0] = highs[0] - lows[0]
    atr14 = pd.Series(tr).rolling(14, min_periods=1).mean().values
    current_atr   = float(atr14[-1])
    current_price = float(closes[-1])

    # Tolerancia: 0.5×ATR como % del precio (adapta a volatilidad)
    tolerance_pct = max(0.002, min(0.008, (0.5 * current_atr) / current_price))

    # ── 2. Detectar pivotes (sin lookahead) ──────────────────────────────────
    peak_indices,   _ = find_peaks( highs, distance=window)
    valley_indices, _ = find_peaks(-lows,  distance=window)

    volumes = df['volume'].values if 'volume' in df.columns else np.ones(len(df))
    avg_vol = float(np.mean(volumes)) if float(np.mean(volumes)) > 0 else 1.0

    # ── 3. Clustering por precio con volume_score ─────────────────────────────
    def cluster_levels(
        prices: np.ndarray,
        indices: np.ndarray,
        tol: float
    ) -> list[dict]:
        if len(prices) == 0:
            return []
        # Ordenar por precio pero mantener el índice original
        order = np.argsort(prices)
        sorted_p = prices[order]
        sorted_i = indices[order]

        clusters: list[tuple[list[float], list[int]]] = []
        cur_p: list[float] = [float(sorted_p[0])]
        cur_i: list[int]   = [int(sorted_i[0])]

        for p, idx in zip(sorted_p[1:], sorted_i[1:]):
            if abs(float(p) - float(np.mean(cur_p))) / float(np.mean(cur_p)) <= tol:
                cur_p.append(float(p))
                cur_i.append(int(idx))
            else:
                clusters.append((cur_p, cur_i))
                cur_p, cur_i = [float(p)], [int(idx)]
        clusters.append((cur_p, cur_i))

        result = []
        for cp, ci in clusters:
            vol_at_pivots = [float(volumes[i]) for i in ci if i < len(volumes)]
            med_vol = float(np.median(vol_at_pivots)) if vol_at_pivots else avg_vol
            result.append({
                'price':        float(np.mean(cp)),
                'touches':      len(cp),
                'zone_top':     float(max(cp)),
                'zone_bottom':  float(min(cp)),
                'volume_score': round(med_vol / avg_vol, 2),  # 1.0 = promedio
            })
        return result

    res_clusters = cluster_levels(highs[peak_indices],   peak_indices,   tolerance_pct)
    sup_clusters = cluster_levels(lows[valley_indices],  valley_indices,  tolerance_pct)


    # ── 4. Detectar si un nivel fue roto en el historial ─────────────────────
    def was_broken(level_price: float, level_type: str) -> bool:
        """
        True si el precio cerró al otro lado del nivel y lo penetró > 0.5×ATR.
        Solo considera cierres para evitar falsas rupturas por wick.
        """
        if level_type == 'RESISTANCE':
            # Resistencia rota si hubo un cierre POR ENCIMA + margen
            return any(c > level_price + 0.3 * current_atr for c in closes)
        else:  # SUPPORT
            return any(c < level_price - 0.3 * current_atr for c in closes)

    # ── 5. Construir lista final con type/origin/strength/is_active ──────────
    def _strength(t: int) -> str:
        if t >= 4: return 'STRONG'
        if t >= 2: return 'MODERATE'
        return 'WEAK'

    all_levels: list[dict] = []

    for r in res_clusters:
        broken = was_broken(r['price'], 'RESISTANCE')
        if not broken:
            # Resistencia válida normal
            all_levels.append({**r, 'type': 'RESISTANCE', 'origin': 'PIVOT',
                                'strength': _strength(r['touches']), 'is_active': True})
        else:
            # Resistencia rota → Role Reversal → ahora es SOPORTE
            all_levels.append({**r, 'type': 'SUPPORT', 'origin': 'ROLE_REVERSAL',
                                'strength': _strength(r['touches']), 'is_active': True})

    for s in sup_clusters:
        broken = was_broken(s['price'], 'SUPPORT')
        if not broken:
            all_levels.append({**s, 'type': 'SUPPORT', 'origin': 'PIVOT',
                                'strength': _strength(s['touches']), 'is_active': True})
        else:
            # Soporte roto → Role Reversal → ahora es RESISTENCIA
            all_levels.append({**s, 'type': 'RESISTANCE', 'origin': 'ROLE_REVERSAL',
                                'strength': _strength(s['touches']), 'is_active': True})

    # ── 6. Separar por tipo y ordenar por proximidad al precio ───────────────
    resistances = sorted(
        [l for l in all_levels if l['type'] == 'RESISTANCE' and l['price'] > current_price],
        key=lambda x: x['price']          # más cercana primero
    )[:num_levels]

    supports = sorted(
        [l for l in all_levels if l['type'] == 'SUPPORT' and l['price'] < current_price],
        key=lambda x: x['price'], reverse=True   # más cercano primero
    )[:num_levels]

    # ── 7. Columnas de compatibilidad ────────────────────────────────────────
    df['resistance_level'] = resistances[0]['price'] if resistances else np.nan
    df['support_level']    = supports[0]['price']    if supports    else np.nan

    # Guardar en attrs para get_key_levels()
    df.attrs['key_resistances'] = resistances
    df.attrs['key_supports']    = supports
    df.attrs['atr_value']       = current_atr

    return df


def get_key_levels(df: pd.DataFrame) -> dict:
    """
    Extrae niveles clave del DataFrame analizado.
    Incluye type, origin, strength, is_active y volume_score.
    """
    def _fmt(levels: list[dict]) -> list[dict]:
        return [{
            'price':         l['price'],
            'touches':       l['touches'],
            'zone_top':      l['zone_top'],
            'zone_bottom':   l['zone_bottom'],
            'type':          l['type'],             # SUPPORT | RESISTANCE
            'origin':        l['origin'],           # PIVOT | ROLE_REVERSAL
            'strength':      l['strength'],         # WEAK | MODERATE | STRONG
            'is_active':     l['is_active'],
            'ob_confluence': l.get('ob_confluence', False),
            'volume_score':  l.get('volume_score', 1.0),
            'mtf_confluence': l.get('mtf_confluence', False),
            'mtf_score':      l.get('mtf_score', 0),
        } for l in levels]

    return {
        'resistances': _fmt(df.attrs.get('key_resistances', [])),
        'supports':    _fmt(df.attrs.get('key_supports',    [])),
        'atr':         df.attrs.get('atr_value', None),
    }

def consolidate_mtf_levels(base_levels: dict, macro_levels: dict, timeframe_weight: int = 2) -> dict:
    """
    Fase 2: Consolidación Multi-Timeframe.
    Cruza los niveles de la temporalidad actual con los de temporalidades mayores.
    Si un nivel macro está cerca de uno base, se marca como confluencia fuerte.
    """
    import numpy as np

    def _process(base_list: list[dict], macro_list: list[dict], atr: float):
        if not atr: return base_list
        for b in base_list:
            for m in macro_list:
                # Si el nivel macro está dentro de 1 ATR del nivel base
                if abs(b['price'] - m['price']) < atr:
                    b['mtf_confluence'] = True
                    b['mtf_score'] += timeframe_weight
                    # El nivel macro aporta sus toques al score mtf
                    b['mtf_score'] += m['touches']
                    if m['touches'] >= 3: b['strength'] = 'STRONG'
        return base_list

    atr = base_levels.get('atr', 0)
    base_levels['resistances'] = _process(base_levels['resistances'], macro_levels.get('resistances', []), atr)
    base_levels['supports']    = _process(base_levels['supports'],    macro_levels.get('supports', []),    atr)
    
    return base_levels




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
