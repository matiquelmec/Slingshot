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
        Detecta el régimen macroestructural del mercado.
        Aplica suavizado EMA, histéresis y filtros de persistencia temporal (v7.0).
        """
        if len(df) < 200:
            return {"regime": "UNKNOWN", "confidence": 0, "atr_norm": 1.0}

        # 1. Base Cálculos: SMA, ATR y ADX (Series Completas)
        close = df['close']
        high = df['high']
        low = df['low']

        # SMA 200 para Sesgo Estructural
        sma_200_series = close.rolling(window=200).mean()

        # ATR (Average True Range) de 14 periodos
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr_14_series = tr.rolling(window=14).mean()
        
        # Normalizacion del ATR
        atr_norm_series = (atr_14_series / close) * 100 

        # Calculo Simplificado del ADX (14 periodos)
        up_move = high.diff()
        down_move = low.shift(1) - low
        
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
        
        plus_dm_14 = pd.Series(plus_dm, index=df.index).rolling(window=14).sum()
        minus_dm_14 = pd.Series(minus_dm, index=df.index).rolling(window=14).sum()
        tr_14_sum = tr.rolling(window=14).sum()
        
        # Prevenir division por cero
        plus_di = 100 * (plus_dm_14 / np.where(tr_14_sum == 0, 1, tr_14_sum))
        minus_di = 100 * (minus_dm_14 / np.where(tr_14_sum == 0, 1, tr_14_sum))
        
        dx = 100 * (abs(plus_di - minus_di) / np.where((plus_di + minus_di) == 0, 1, (plus_di + minus_di)))
        adx_14_series = pd.Series(dx, index=df.index).rolling(window=14).mean()

        # ── 2. Suavizado Exponencial (EMA 5) para mitigar ruido intradiario ──
        adx_smooth = adx_14_series.ewm(span=5, adjust=False).mean()
        plus_di_smooth = pd.Series(plus_di, index=df.index).ewm(span=5, adjust=False).mean()
        minus_di_smooth = pd.Series(minus_di, index=df.index).ewm(span=5, adjust=False).mean()

        # ── 3. Simulación Histórica de Regímenes con Histéresis ──
        raw_regimes = []
        is_trending = False  # Estado inicial de tendencia

        for idx in range(len(df)):
            if idx < 200:
                raw_regimes.append("UNKNOWN")
                continue

            cur_price = close.iloc[idx]
            cur_sma = sma_200_series.iloc[idx]
            cur_adx = adx_smooth.iloc[idx]
            cur_plus_di = plus_di_smooth.iloc[idx]
            cur_minus_di = minus_di_smooth.iloc[idx]
            cur_atr_norm = atr_norm_series.iloc[idx]

            bias = "BULLISH" if cur_price > cur_sma else "BEARISH"

            # Logica de Histéresis: Buffer entre 18 y 22 para evitar oscilaciones rápidas
            if cur_adx > 22:
                is_trending = True
            elif cur_adx < 18:
                is_trending = False
            # Si está entre 18 y 22, mantiene su estado anterior (is_trending)

            # Clasificación de régimen bruto (raw)
            if not is_trending:
                regime = "CHOPPY"
            elif 20 <= cur_adx < 40:
                if bias == "BULLISH" and cur_plus_di > cur_minus_di:
                    regime = "TRENDING_BULL"
                elif bias == "BEARISH" and cur_minus_di > cur_plus_di:
                    regime = "TRENDING_BEAR"
                else:
                    regime = "TRANSITION"
            else:  # cur_adx >= 40
                if bias == "BULLISH":
                    regime = "STRONG_BULL"
                else:
                    regime = "STRONG_BEAR"

            # Estrés de alta volatilidad
            if cur_atr_norm > 1.5:
                regime = "HIGH_VOLATILITY_STRESS"

            raw_regimes.append(regime)

        # ── 4. Filtro de Persistencia Temporal (Confirmación por Ventana de 3 Velas) ──
        persistent_regimes = []
        last_persistent = "UNKNOWN"

        for idx in range(len(df)):
            if idx < 202:
                persistent_regimes.append(raw_regimes[idx])
                if raw_regimes[idx] != "UNKNOWN":
                    last_persistent = raw_regimes[idx]
                continue

            # Si las últimas 3 velas tienen exactamente el mismo régimen bruto, se confirma la transición
            window_regimes = raw_regimes[idx-2:idx+1]
            if len(set(window_regimes)) == 1:
                last_persistent = window_regimes[-1]

            persistent_regimes.append(last_persistent)

        # Retornar veredicto estabilizado del último índice
        final_regime = persistent_regimes[-1]
        final_adx = adx_smooth.iloc[-1]
        final_atr_norm = atr_norm_series.iloc[-1]
        final_bias = "BULLISH" if close.iloc[-1] > sma_200_series.iloc[-1] else "BEARISH"
        confidence = round(min(final_adx * 2, 100), 2)

        return {
            "regime": final_regime,
            "bias": final_bias,
            "adx_score": round(final_adx, 2),
            "atr_norm": round(final_atr_norm, 4),
            "confidence": confidence
        }

# Singleton instance
market_analyzer = MarketAnalyzer()
