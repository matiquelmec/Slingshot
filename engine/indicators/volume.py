from engine.core.logger import logger
import pandas as pd
import numpy as np
from scipy import stats

def _format_pandas_freq(interval: str) -> str:
    """Sanea el intervalo para compatibilidad con Pandas 2.2.0+"""
    if not interval: return None
    mapping = {'1m': '1min', '3m': '3min', '5m': '5min', '15m': '15min', '30m': '30min', '1h': '1h', '4h': '4h', '1d': '1D'}
    return mapping.get(interval, interval.replace('m', 'min') if interval.endswith('m') else interval)

def calculate_seasonal_volume(df: pd.DataFrame, window_days: int = 5) -> pd.Series:
    """
    Normalización por Estacionalidad v8.0 (Institutional Apex).
    Compara el volumen actual con el promedio histórico de su misma franja horaria.
    """
    if 'timestamp' not in df.columns or len(df) < 100:
        return pd.Series(df['volume'].median(), index=df.index)
    
    temp_df = df.copy()
    temp_df['dt'] = pd.to_datetime(temp_df['timestamp'], unit='ms', errors='coerce')
    temp_df['hour'] = temp_df['dt'].dt.hour
    temp_df['minute'] = temp_df['dt'].dt.minute
    
    # Calculamos cuántas muestras hay por slot
    slot_counts = temp_df.groupby(['hour', 'minute'])['volume'].transform('count')
    seasonal_profile = temp_df.groupby(['hour', 'minute'])['volume'].transform('mean')
    
    # Si tenemos menos de 2 muestras para un slot, la estacionalidad no es confiable
    # Usamos la mediana global del dataframe como fallback para esos slots
    global_median = temp_df['volume'].median()
    seasonal_profile = np.where(slot_counts >= 2, seasonal_profile, global_median)
    
    return pd.Series(seasonal_profile, index=df.index)

def calculate_rvol(df: pd.DataFrame, window: int = 50, use_seasonality: bool = True, target_interval: str = None) -> pd.DataFrame:
    """
    Relative Volume (RVOL) Apex Edition.
    Usa Rango Percentil (0-100) y Estacionalidad para una lectura no-lineal.
    """
    df = df.copy()
    if df.empty: return df

    # 1. Obtener Base de Comparación (Estacional o Mediana)
    # [ROBUSTEZ v8.1] Solo usamos estacionalidad si el buffer cubre al menos 24 horas
    has_enough_history = False
    if 'timestamp' in df.columns and len(df) > 10:
        diff = df['timestamp'].max() - df['timestamp'].min()
        # Manejo robusto: Si es Timedelta (datetime) o si es numérico (ms)
        if hasattr(diff, 'total_seconds'):
            duration_hours = diff.total_seconds() / 3600
        else:
            duration_hours = diff / (1000 * 60 * 60)
            
        if duration_hours >= 23.5:
            has_enough_history = True

    if use_seasonality and has_enough_history:
        df['vol_median'] = calculate_seasonal_volume(df)
    else:
        # Fallback a Mediana Móvil Robusta si no hay historial suficiente para estacionalidad
        df['vol_median'] = df['volume'].rolling(window=window, min_periods=10).median()
    
    # Asegurar que el median no sea cero (Protección Anti-Explosión)
    global_median = df['volume'].median()
    df['vol_median'] = df['vol_median'].replace(0, global_median).fillna(global_median)
    
    # 2. Ratio Crudo
    df['rvol_ratio'] = df['volume'] / (df['vol_median'] + 1e-9)
    
    # 3. Normalización por Rango Percentil (Robusto contra Outliers)
    # Indica qué tan alto es el volumen actual respecto al historial (0.0 a 1.0)
    df['rvol_pct'] = df['volume'].rolling(window=window*2, min_periods=20).rank(pct=True)
    
    # RVOL Final para el Dashboard (Escala Humana 0x - 5x)
    df['rvol'] = df['rvol_ratio'].clip(0, 5.0)
    
    return df

def calculate_order_flow_delta(df: pd.DataFrame) -> pd.Series:
    """
    Order Flow Delta Ingestion Engine v10.0.
    Calcula la fuerza neta compradora vs vendedora a nivel de mecha, cuerpo y datos del Sidecar.
    Retorna Series con valores entre -1.0 (Venta pura) y +1.0 (Compra pura).
    """
    if df.empty or 'close' not in df.columns or 'open' not in df.columns:
        return pd.Series(0.0, index=df.index if not df.empty else None)

    body = df['close'] - df['open']
    high_low = df['high'] - df['low']
    high_low_safe = high_low.replace(0, 1e-9)

    # Delta direccional basado en cuerpo y mechas
    wick_delta = body / high_low_safe

    # Si la columna delta_ratio del Sidecar está presente, combinar con mayor peso
    if 'delta_ratio' in df.columns:
        sidecar_delta = df['delta_ratio'].fillna(0.0)
        combined = (sidecar_delta * 0.6) + (wick_delta * 0.4)
    else:
        combined = wick_delta

    return combined.clip(-1.0, 1.0)

def calculate_cvd_divergence(df: pd.DataFrame, window: int = 30) -> dict:
    """
    Cumulative Volume Delta (CVD) Divergence & Institutional Imbalance Engine v11.0.
    Rastrear el acumulado de volumen delta vs tendencia de precio para identificar absorciones masivas.
    """
    if df.empty or len(df) < window or 'close' not in df.columns:
        return {"status": "NEUTRAL", "cvd_slope": 0.0, "price_slope": 0.0, "divergence": None}

    delta_series = calculate_order_flow_delta(df)
    volume_series = df['volume']
    
    # CVD en unidades de volumen delta acumulado
    cvd_raw = (delta_series * volume_series).cumsum()
    
    recent_price = df['close'].iloc[-window:]
    recent_cvd = cvd_raw.iloc[-window:]
    
    # Pendientes de precio y CVD (normalizados)
    x = np.arange(window)
    price_slope = float(np.polyfit(x, recent_price / float(recent_price.iloc[0]), 1)[0])
    cvd_base = float(recent_cvd.iloc[0]) if float(recent_cvd.iloc[0]) != 0 else 1.0
    cvd_slope = float(np.polyfit(x, (recent_cvd - cvd_base) / abs(cvd_base + 1e-9), 1)[0])
    
    # Divergencias Institucionales
    # 1. Bullish CVD Divergence (Precio cae pero CVD sube -> Absorción Compradora)
    if price_slope < -0.0001 and cvd_slope > 0.0001:
        status = "BULLISH_DIVERGENCE"
    # 2. Bearish CVD Divergence (Precio sube pero CVD cae -> Absorción Vendedora / Distribución)
    elif price_slope > 0.0001 and cvd_slope < -0.0001:
        status = "BEARISH_DIVERGENCE"
    else:
        status = "IN_SYNC"
        
    return {
        "status": status,
        "price_slope": round(price_slope, 6),
        "cvd_slope": round(cvd_slope, 6),
        "cvd_value": float(recent_cvd.iloc[-1])
    }

def calculate_absorption_index(df: pd.DataFrame, window: int = 50, target_interval: str = None) -> pd.DataFrame:
    """
    VSA Intelligence Engine v8.0.
    Mide 'Esfuerzo (Volumen)' vs 'Resultado (Precio)'.
    Escala: 0-100 (Donde > 80 es Absorción Extrema / Smart Money Accumulation).
    """
    df = df.copy()
    if len(df) < 20: return df

    # Inyección de Order Flow Delta
    df['order_flow_delta'] = calculate_order_flow_delta(df)

    # 1. Esfuerzo (Volumen Relativo)
    vol_median = df['volume'].rolling(window=window, min_periods=20).median()
    effort = df['volume'] / (vol_median + 1e-9)
    
    # 2. Resultado (Spread de la vela relativo a la volatilidad ATR)
    # Usamos ATR para que el "resultado" sea comparable en cualquier mercado/TF
    high_low = df['high'] - df['low']
    close_prev = df['close'].shift(1)
    tr = np.maximum(high_low, np.abs(df['high'] - close_prev), np.abs(df['low'] - close_prev))
    atr = pd.Series(tr).rolling(window=20).mean()
    
    body_spread = (df['close'] - df['open']).abs()
    result = body_spread / (atr + 1e-9)
    
    # 3. [NUEVA LOGICA DETERMINISTA] Institutional Absorption Ratio
    # En lugar de Z-Scores volátiles, usamos ratios físicos de Esfuerzo vs Resultado.
    
    # A. RelVol: ¿Cuántas veces el volumen actual supera a la mediana?
    rel_vol = effort / (effort.rolling(window=window).median() + 1e-9)
    
    # B. RelSpread: ¿Cuántas veces el movimiento actual supera al ATR?
    # Usamos un floor de 0.1 para evitar que dojis disparen el ratio al infinito.
    rel_spread = result / (result.rolling(window=window).median() + 0.1)
    
    # C. Apex Factor: El ratio puro de absorción.
    # Un factor de 1.0 significa equilibrio. > 2.0 significa absorción institucional clara.
    apex_factor = rel_vol / (rel_spread + 0.1)
    
    # [FIX v13.1] Sanitizar Inf/NaN antes del sigmoid para garantizar rango 0-100
    apex_factor = apex_factor.replace([np.inf, -np.inf], np.nan).fillna(1.0).clip(0, 10)
    
    # 4. Mapeo a Escala 0-100 (Log-Sigmoid)
    # Calibrado para que Factor 1.0 -> Score 50, Factor 3.0 -> Score 85, Factor 5.0 -> Score 95
    raw_score = (1 / (1 + np.exp(-(apex_factor - 1.0) * 1.5))) * 100
    df['absorption_score'] = raw_score.clip(0, 100).fillna(50.0)  # Garantia de rango estricto
    
    # Metadatos
    df['absorption_raw'] = apex_factor
    
    return df


def calculate_volume_profile(df: pd.DataFrame, bins: int = 50) -> dict:
    """
    Volume Profile v1.0 — Distribución de Volumen por Precio.
    Calcula: POC, Value Area High (VAH), Value Area Low (VAL), LVNs.
    Compatible con el pipeline táctico existente.
    """
    if df.empty or len(df) < 20:
        return {"poc": 0, "vah": 0, "val": 0, "lvns": [], "hvns": []}
    
    # 1. Construir el histograma precio × volumen
    price_min = float(df["low"].min())
    price_max = float(df["high"].max())
    
    if price_min == price_max:
        return {"poc": price_min, "vah": price_min, "val": price_min, "lvns": [], "hvns": []}

    price_bins = np.linspace(price_min, price_max, bins + 1)
    vol_at_price = np.zeros(bins)
    
    for _, row in df.iterrows():
        # Lógica de Intersección: una vela alimenta todos los bins que toca
        # Aseguramos que al menos un bin sea capturado (el que contiene el close)
        candle_bins = np.where(
            (price_bins[1:] >= row["low"]) & (price_bins[:-1] <= row["high"])
        )[0]
        
        if len(candle_bins) > 0:
            vol_per_bin = row["volume"] / len(candle_bins)
            vol_at_price[candle_bins] += vol_per_bin
        else:
            # Fallback: asignar al bin que contiene el close si la vela es muy pequeña
            idx = np.searchsorted(price_bins, row["close"]) - 1
            idx = max(0, min(idx, bins - 1))
            vol_at_price[idx] += row["volume"]
    
    # 2. POC (Point of Control): Precio con mayor volumen
    poc_idx = np.argmax(vol_at_price)
    poc = float((price_bins[poc_idx] + price_bins[poc_idx + 1]) / 2)
    
    # 3. Value Area (70% del volumen total, expandiendo desde el POC)
    total_vol = vol_at_price.sum()
    if total_vol <= 0:
        return {"poc": poc, "vah": poc, "val": poc, "lvns": [], "hvns": []}

    target_vol = total_vol * 0.70
    accumulated = vol_at_price[poc_idx]
    lo, hi = poc_idx, poc_idx
    
    while accumulated < target_vol and (lo > 0 or hi < bins - 1):
        expand_up = vol_at_price[hi + 1] if hi < bins - 1 else 0
        expand_dn = vol_at_price[lo - 1] if lo > 0 else 0
        if expand_up >= expand_dn:
            hi += 1
            accumulated += expand_up
        else:
            lo -= 1
            accumulated += expand_dn
    
    vah = float(price_bins[hi + 1])
    val = float(price_bins[lo])
    
    # 4. Low Volume Nodes (LVN): Zonas de rechazo (Mínimos Locales)
    lvns = []
    for i in range(1, bins - 1):
        # Un LVN es un mínimo local: menor que sus vecinos y menor que el promedio
        if vol_at_price[i] < vol_at_price[i-1] and vol_at_price[i] < vol_at_price[i+1]:
            if vol_at_price[i] < (total_vol / bins) * 0.5:
                lvns.append(float((price_bins[i] + price_bins[i + 1]) / 2))
    
    # 5. Absorption Score (Esfuerzo vs Resultado)
    # Si el volumen es alto pero el rango de la vela es pequeño = Absorción
    last_candles = df.tail(5)
    vol_mean = last_candles["volume"].mean()
    range_mean = (last_candles["high"] - last_candles["low"]).mean()
    
    # Ponderación institucional: Alta si vol > avg y range < avg
    absorption_score = 0
    if vol_mean > 0 and range_mean > 0:
        absorption_score = (vol_mean / range_mean) * 0.001 # Normalizado
        absorption_score = min(float(absorption_score), 100.0) # Cap at 100

    return {
        "poc":  round(poc, 5),
        "vah":  round(vah, 5),
        "val":  round(val, 5),
        "lvns": [round(x, 5) for x in sorted(lvns, key=lambda p: vol_at_price[np.argmin(np.abs(price_bins - p))])[:3]],
        "absorption_score": round(absorption_score, 2)
    }


def analyze_volume_footprint(df: pd.DataFrame) -> pd.DataFrame:
    """Analiza la firma del volumen con lógica VSA."""
    df = df.copy()
    
    # 1. Detección de Clímax (Basado en Desviación Estándar Robusta)
    vol = df['volume']
    mean_vol = vol.rolling(window=50).mean()
    std_vol = vol.rolling(window=50).std()
    df['is_climax_vol'] = vol > (mean_vol + (std_vol * 2.5))
    
    # 2. Inyección de Inteligencia de Absorción
    df = calculate_absorption_index(df)
    
    return df

def confirm_trigger(df: pd.DataFrame, min_rvol_pct: float = 0.85) -> pd.DataFrame:
    """
    Gatillo Institucional Apex Edition.
    Valida si el volumen actual es parte de un movimiento orquestado por el Smart Money.
    """
    df = calculate_rvol(df)
    df = analyze_volume_footprint(df)
    
    # Filtro de Outliers destructivos
    vol_median = df['volume'].rolling(window=50).median()
    df['is_outlier_error'] = df['volume'] > (vol_median * 15.0) # Error de feed si es > 15x la mediana
    
    # Veredicto Apex:
    # 1. El volumen debe estar en el top 15% (Percentile Rank > 0.85)
    # 2. No debe ser un error de feed
    # 3. Debe haber una absorción significativa (> 70) o ser un Clímax validado.
    df['valid_trigger'] = (df['rvol_pct'] >= min_rvol_pct) & \
                          (~df['is_outlier_error']) & \
                          ((df['absorption_score'] > 70) | (df['is_climax_vol']))
    
    # Señales de Absorción de Elite para el Dashboard
    df['is_absorption_elite'] = (df['absorption_score'] > 85) & (df['rvol_pct'] > 0.70)
    
    return df

if __name__ == "__main__":
    import time
    start = time.time()
    
    # Simulación de estrés (1,000 velas)
    test_df = pd.DataFrame({
        'timestamp': pd.date_range(start='2024-01-01', periods=1000, freq='15min'),
        'open': np.random.uniform(50000, 51000, 1000),
        'high': np.random.uniform(51000, 52000, 1000),
        'low': np.random.uniform(49000, 50000, 1000),
        'close': np.random.uniform(50000, 51000, 1000),
        'volume': np.random.uniform(100, 1000, 1000)
    })
    
    result = confirm_trigger(test_df)
    
    end = time.time()
    logger.info(f"💎 [APEX] Kernel de Volumen v8.0 optimizado en {(end-start)*1000:.2f}ms")
    logger.info(f"Velas Elite detectadas: {len(result[result['is_absorption_elite']])}")
    if not result.empty:
        last = result.iloc[-1]
        logger.info(f"Estado Final -> RVOL Pct: {last['rvol_pct']:.2%}, Absorción: {last['absorption_score']:.2f}")
