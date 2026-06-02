"""
engine/strategies/larry_williams.py — v1.0.0 (Larry Williams "Oops! Reversal" Strategy)
=============================================================================
Implementación institucional de la estrategia de reversión por falsos rompimientos
de niveles diarios (PDH/PDL) de Larry Williams.
"""
import pandas as pd
import numpy as np
from engine.core.logger import logger

class LarryWilliamsOopsStrategy:
    """
    Estrategia Larry Williams Oops! Reversal.
    Detecta capitulaciones y falsos rompimientos por debajo del PDL (Previous Day Low)
    o por encima del PDH (Previous Day High), generando señales de alta probabilidad en la reversión.
    """
    
    def __init__(self):
        pass

    def analyze(self, df: pd.DataFrame, interval: str = "15m") -> pd.DataFrame:
        if df.empty or len(df) < 10:
            return df

        df = df.copy()

        # Asegurar tipo datetime
        if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
            df['timestamp'] = pd.to_datetime(df['timestamp'])

        # Calcular PDH/PDL de forma dinámica agrupando por día UTC
        try:
            df['date_utc'] = df['timestamp'].dt.date
            daily_stats = df.groupby('date_utc').agg(
                daily_high=('high', 'max'),
                daily_low=('low', 'min')
            )
            # Desplazar 1 día para obtener los niveles de "ayer"
            daily_stats_shifted = daily_stats.shift(1)
            
            # Combinar con el dataframe principal
            df = df.merge(daily_stats_shifted, left_on='date_utc', right_index=True, how='left')
            df.rename(columns={'daily_high': 'pdh', 'daily_low': 'pdl'}, inplace=True)
            df.drop(columns=['date_utc'], inplace=True, errors='ignore')
        except Exception as e:
            logger.warning(f"[LARRY_WILLIAMS] Error calculando PDH/PDL dinámico: {e}. Usando fallback.")
            # Fallback simple basado en rolling window de 24 horas (aprox 96 velas de 15m)
            lookback = 96
            df['pdh'] = df['high'].rolling(window=lookback).max().shift(1)
            df['pdl'] = df['low'].rolling(window=lookback).min().shift(1)

        # Rellenar valores nulos iniciales para evitar fallas
        df['pdh'] = df['pdh'].ffill().bfill()
        df['pdl'] = df['pdl'].ffill().bfill()

        # Calcular Williams %R (14 periodos)
        highest_high = df['high'].rolling(14).max()
        lowest_low = df['low'].rolling(14).min()
        df['williams_r'] = ((highest_high - df['close']) / (highest_high - lowest_low + 1e-9)) * -100
        df['williams_r'] = df['williams_r'].ffill().bfill()

        # Calcular ATR robusto para Stops y Targets
        if 'atr' not in df.columns:
            high_low = df["high"] - df["low"]
            high_close = (df["high"] - df["close"].shift()).abs()
            low_close = (df["low"] - df["close"].shift()).abs()
            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            true_range = ranges.max(axis=1)
            df["atr"] = true_range.ewm(alpha=1/14, adjust=False).mean()

        df['rvol_robust'] = df['volume'] / (df['volume'].rolling(20).mean() + 1e-9)

        return df

    def find_opportunities(self, df: pd.DataFrame, asset: str = "UNKNOWN") -> list[dict]:
        if df.empty or len(df) < 10:
            return []

        # Asegurar que existan PDH/PDL
        if 'pdh' not in df.columns or 'pdl' not in df.columns:
            df = self.analyze(df)

        opportunities = []
        last_idx = len(df) - 1
        
        # Lógica Oops! en cripto:
        # LONG: Mínimo menor al PDL, pero el cierre recupera el PDL (falso rompimiento de soporte)
        # SHORT: Máximo mayor al PDH, pero el cierre vuelve abajo del PDH (falso rompimiento de resistencia)
        
        oops_long = (df['low'] < df['pdl']) & (df['close'] > df['pdl'])
        oops_short = (df['high'] > df['pdh']) & (df['close'] < df['pdh'])
        
        # Filtro de volumen adicional: la vela gatillo debe mostrar cierta absorción
        # Exigimos un volumen relativo aceptable para filtrar ruido
        rvol_filter = df['rvol_robust'] > 0.8
        
        long_triggered = oops_long & rvol_filter
        short_triggered = oops_short & rvol_filter

        if last_idx in np.where(long_triggered | short_triggered)[0]:
            sig_type = "LONG" if long_triggered[last_idx] else "SHORT"
            sig = self._format_signal(last_idx, sig_type, df.iloc[last_idx], asset)
            sig["conviction"] = 0.80
            sig["tier"] = "A"
            opportunities.append(sig)

        return opportunities

    def _format_signal(self, idx: int, signal_type: str, candle: pd.Series, asset: str) -> dict:
        # Larry Williams Oops! entra en el cruce de vuelta del nivel roto
        # Entrada: PDL para Longs, PDH para Shorts (Sniper entry institucional)
        pdl_val = float(candle['pdl'])
        pdh_val = float(candle['pdh'])
        entry_p = pdl_val if signal_type == "LONG" else pdh_val
        
        # Si el precio actual está muy lejos, forzar entrada al precio de cierre actual
        close_p = float(candle['close'])
        if abs(close_p - entry_p) / close_p > 0.02:
            entry_p = close_p
            
        return {
            "index": int(idx),
            "asset": asset,
            "symbol": asset,
            "type": "Oops! Reversal",
            "signal_type": signal_type,
            "price": entry_p,
            "stop_loss": 0,    # Calculado por el RiskManager
            "take_profit_3r": 0,
            "timestamp": str(candle['timestamp']) if 'timestamp' in candle else 0,
            "conviction": 0.80,
            "rvol": float(candle.get('rvol_robust', 1.0)),
            "williams_r": float(candle.get('williams_r', -50.0)),
            "atr_value": float(candle.get('atr', entry_p * 0.002))
        }
