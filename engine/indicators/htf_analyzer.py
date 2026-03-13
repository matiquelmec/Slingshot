import pandas as pd
from dataclasses import dataclass
from engine.indicators.regime import RegimeDetector

@dataclass
class HTFBias:
    direction: str   # 'BULLISH' | 'BEARISH' | 'NEUTRAL'
    strength: float  # 0.0 - 1.0
    reason: str      # e.g. "4H MARKUP + 1H Order Block Alcista"
    h4_regime: str
    h1_regime: str

class HTFAnalyzer:
    """
    Analizador de Timeframes Superiores (4H + 1H).
    Determina el sesgo direccional institucional para filtrar señales tácticas.
    """
    def __init__(self):
        self.regime_detector = RegimeDetector()

    def analyze_bias(self, df_h4: pd.DataFrame, df_h1: pd.DataFrame) -> HTFBias:
        """
        Analiza el sesgo top-down basado en los regímenes de 4H y 1H.
        """
        if df_h4.empty or df_h1.empty:
            return HTFBias(
                direction='NEUTRAL',
                strength=0.0,
                reason="Datos HTF insuficientes.",
                h4_regime='UNKNOWN',
                h1_regime='UNKNOWN'
            )

        # Detectar regímenes
        df_h4 = self.regime_detector.detect_regime(df_h4)
        df_h1 = self.regime_detector.detect_regime(df_h1)

        h4_regime = df_h4['market_regime'].iloc[-1]
        h1_regime = df_h1['market_regime'].iloc[-1]

        # Lógica de Sesgo Direccional
        direction = 'NEUTRAL'
        strength = 0.5
        reason = "Contexto HTF indeciso o ruidoso."

        # BULLISH CONDITIONS
        if h4_regime == 'MARKUP':
            if h1_regime in ['MARKUP', 'ACCUMULATION', 'RANGING']:
                direction = 'BULLISH'
                strength = 1.0 if h1_regime == 'MARKUP' else 0.8
                reason = f"4H MARKUP + {h1_regime} en 1H. Sesgo institucional alcista."
            else:
                direction = 'BULLISH'
                strength = 0.6
                reason = "4H MARKUP pero 1H en corrección/incertidumbre."
        
        # BEARISH CONDITIONS
        elif h4_regime == 'MARKDOWN':
            if h1_regime in ['MARKDOWN', 'DISTRIBUTION', 'RANGING']:
                direction = 'BEARISH'
                strength = 1.0 if h1_regime == 'MARKDOWN' else 0.8
                reason = f"4H MARKDOWN + {h1_regime} en 1H. Sesgo institucional bajista."
            else:
                direction = 'BEARISH'
                strength = 0.6
                reason = "4H MARKDOWN pero 1H en rebote/incertidumbre."

        # TRANSITION / ACCUMULATION
        elif h4_regime == 'ACCUMULATION':
            if h1_regime in ['ACCUMULATION', 'MARKUP']:
                direction = 'BULLISH'
                strength = 0.7
                reason = "4H ACCUMULATION + 1H iniciando ciclo alcista."
            else:
                direction = 'NEUTRAL'
                strength = 0.4
                reason = "4H ACCUMULATION. Aún sin confirmación en 1H."

        elif h4_regime == 'DISTRIBUTION':
            if h1_regime in ['DISTRIBUTION', 'MARKDOWN']:
                direction = 'BEARISH'
                strength = 0.7
                reason = "4H DISTRIBUTION + 1H iniciando ciclo bajista."
            else:
                direction = 'NEUTRAL'
                strength = 0.4
                reason = "4H DISTRIBUTION. Aún sin confirmación en 1H."

        return HTFBias(
            direction=direction,
            strength=strength,
            reason=reason,
            h4_regime=h4_regime,
            h1_regime=h1_regime
        )
