"""
engine/indicators/regime.py — v6.0.6 (Wyckoff Professional Edition)
==================================================================
Detector de Régimen de Mercado basado en Eficiencia y Estructura Fractal.
Alineado con los principios de Oferta y Demanda de Smart Money Concepts.
"""
import pandas as pd
import numpy as np
from engine.core.logger import logger

class RegimeDetector:
    def __init__(self, window: int = 50):
        self.window = window

    def detect_regime(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or len(df) < self.window:
            df['market_regime'] = 'UNKNOWN'
            return df

        df = df.copy()

        # 1. Métricas de Eficiencia del Precio (Kaufman Efficiency Ratio)
        # mide qué tan 'directo' es el movimiento. 1.0 = Línea recta.
        change = abs(df['close'] - df['close'].shift(self.window))
        volatility = abs(df['close'] - df['close'].shift(1)).rolling(window=self.window).sum()
        df['efficiency'] = change / (volatility + 1e-9)

        # 2. Estructura de Tendencia (Highs/Lows)
        rolling_high = df['high'].rolling(window=self.window).max()
        rolling_low = df['low'].rolling(window=self.window).min()
        range_size = rolling_high - rolling_low
        df['pos_pct'] = (df['close'] - rolling_low) / (range_size + 1e-9)

        # 3. Momentum de largo plazo
        df['mom_long'] = df['close'].diff(self.window)

        # ── 4. LÓGICA DE DECISIÓN INSTITUCIONAL ──
        df['market_regime'] = 'RANGING' # Estado por defecto

        # A. EXPANSIÓN (Tendencia clara y eficiente)
        mask_markup = (df['mom_long'] > 0) & (df['efficiency'] > 0.3)
        mask_markdown = (df['mom_long'] < 0) & (df['efficiency'] > 0.3)
        
        # B. RANGOS DE ALTA PROBABILIDAD (Wyckoff Accum/Distrib)
        # Si la eficiencia es baja (< 0.3) pero estamos en extremos del rango
        mask_accum = (df['efficiency'] <= 0.3) & (df['pos_pct'] < 0.3)
        mask_distrib = (df['efficiency'] <= 0.3) & (df['pos_pct'] > 0.7)

        # C. CHOPPY (El verdadero ruido: Eficiencia bajísima + volatilidad errática)
        # Si el precio no avanza nada tras 50 velas y se mueve mucho entre medio
        mask_choppy = (df['efficiency'] < 0.1)

        # Aplicar máscaras en orden de prioridad
        df.loc[mask_markup, 'market_regime'] = 'MARKUP'
        df.loc[mask_markdown, 'market_regime'] = 'MARKDOWN'
        df.loc[mask_accum, 'market_regime'] = 'ACCUMULATION'
        df.loc[mask_distrib, 'market_regime'] = 'DISTRIBUTION'
        df.loc[mask_choppy, 'market_regime'] = 'CHOPPY'

        # Fallback de seguridad
        df['market_regime'] = df['market_regime'].fillna('RANGING')
        
        return df

if __name__ == "__main__":
    # Simulación de test
    logger.info("Detector v6.0.6 cargado.")
