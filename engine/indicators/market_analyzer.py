"""
engine/indicators/market_analyzer.py — v6.1.0 (Strategy Delta Delta)
==============================================================
Analizador de Mercado Compuesto: Fusion de Tendencia, Momentum y Volatilidad.
Proporciona un veredicto de regimen de mercado para optimizar la seleccion de algoritmos.
"""
import pandas as pd
import numpy as np
from engine.core.logger import logger

class MarketAnalyzer:
    """
    FASE 2: INDICADOR DE REGIMEN COMPUESTO
    Detecta el regimen macroestructural del mercado fusionando:
    1. Trend Filter (SMA 200)
    2. Momentum Direction (ADX + DI)
    3. Friccion Volatil (ATR)
    """

    def detect_market_regime(self, df: pd.DataFrame) -> dict:
        """
        Detecta el regimen macroestructural del mercado.
        """
        if len(df) < 200:
            return {"regime": "UNKNOWN", "confidence": 0, "atr_norm": 1.0}

        # 1. Base Calculos: SMA, ATR y ADX
        close = df['close']
        high = df['high']
        low = df['low']

        # SMA 200 para Sesgo Estructural
        sma_200 = close.rolling(window=200).mean().iloc[-1]
        current_price = close.iloc[-1]
        structural_bias = "BULLISH" if current_price > sma_200 else "BEARISH"

        # ATR (Average True Range) de 14 periodos
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr_14 = tr.rolling(window=14).mean().iloc[-1]
        
        # Normalizacion del ATR para ajustar dinamicamente los Stops
        atr_norm = (atr_14 / current_price) * 100 

        # Calculo Simplificado del ADX (14 periodos)
        up_move = high.diff()
        down_move = low.shift(1) - low
        
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
        
        plus_dm_14 = pd.Series(plus_dm).rolling(window=14).sum()
        minus_dm_14 = pd.Series(minus_dm).rolling(window=14).sum()
        tr_14_sum = tr.rolling(window=14).sum()
        
        # Prevenir division por cero
        plus_di = 100 * (plus_dm_14 / np.where(tr_14_sum == 0, 1, tr_14_sum))
        minus_di = 100 * (minus_dm_14 / np.where(tr_14_sum == 0, 1, tr_14_sum))
        
        dx = 100 * (abs(plus_di - minus_di) / np.where((plus_di + minus_di) == 0, 1, (plus_di + minus_di)))
        adx_14 = pd.Series(dx).rolling(window=14).mean().iloc[-1]

        # 2. Logica de Clasificacion Institucional
        regime = "UNKNOWN"
        confidence = round(min(adx_14 * 2, 100), 2) # Escalar el ADX a un pseudo % de confianza

        if adx_14 < 20:
            regime = "CHOPPY" # Rango lateral, alta friccion.
        elif 20 <= adx_14 < 40:
            if structural_bias == "BULLISH" and plus_di.iloc[-1] > minus_di.iloc[-1]:
                 regime = "TRENDING_BULL"
            elif structural_bias == "BEARISH" and minus_di.iloc[-1] > plus_di.iloc[-1]:
                 regime = "TRENDING_BEAR"
            else:
                 regime = "TRANSITION" # Choque entre sesgo largo plazo y momentum corto plazo.
        else: # adx_14 >= 40
            if structural_bias == "BULLISH":
                regime = "STRONG_BULL"
            else:
                regime = "STRONG_BEAR"

        # Deteccion de Volatilidad Extrema (Si ATR estalla, forzamos regimen turbulento)
        # Asumimos que un movimiento del >1.5% promedio en 14 velas es alta volatilidad para TF cortos
        if atr_norm > 1.5: 
            regime = "HIGH_VOLATILITY_STRESS"

        return {
            "regime": regime,
            "bias": structural_bias,
            "adx_score": round(adx_14, 2),
            "atr_norm": round(atr_norm, 4),
            "confidence": confidence
        }

# Singleton instance
market_analyzer = MarketAnalyzer()
