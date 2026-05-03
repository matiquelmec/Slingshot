import pandas as pd
from dataclasses import dataclass
from engine.indicators.regime import RegimeDetector

@dataclass
class HTFBias:
    direction: str   # 'BULLISH' | 'BEARISH' | 'NEUTRAL'
    strength: float  # 0.0 - 1.0
    reason: str      # e.g. "1D MARKUP + 4H MARKUP"
    m1_regime: str
    w1_regime: str
    d1_regime: str
    h4_regime: str
    h1_regime: str
    pdh: float = 0.0 # Previous Daily High
    pdl: float = 0.0 # Previous Daily Low
    pwh: float = 0.0 # Previous Weekly High
    pwl: float = 0.0 # Previous Weekly Low

class HTFAnalyzer:
    """
    Analizador de Timeframes Superiores (4H + 1H).
    Determina el sesgo direccional institucional para filtrar señales tácticas.
    """
    def __init__(self):
        self.regime_detector = RegimeDetector()

    def analyze_bias(self, df_1m: pd.DataFrame, df_1w: pd.DataFrame, df_1d: pd.DataFrame, df_h4: pd.DataFrame, df_h1: pd.DataFrame) -> HTFBias:
        """
        Analiza el sesgo top-down (Mensual -> Semanal -> Diario -> 4H -> 1H) e identifica liquidez magnética.
        """
        if df_1d.empty or df_h4.empty or df_h1.empty:
            return HTFBias(
                direction='NEUTRAL', strength=0.0, reason="Datos HTF insuficientes.",
                m1_regime='UNKNOWN', w1_regime='UNKNOWN', d1_regime='UNKNOWN', h4_regime='UNKNOWN', h1_regime='UNKNOWN'
            )

        # Extraer PDH / PDL (Previous Daily High / Low)
        pdh, pdl = 0.0, 0.0
        if len(df_1d) >= 2:
            pdh = float(df_1d.iloc[-2]['high'])
            pdl = float(df_1d.iloc[-2]['low'])

        # Extraer PWH / PWL (Previous Weekly High / Low)
        pwh, pwl = 0.0, 0.0
        if not df_1w.empty and len(df_1w) >= 2:
            pwh = float(df_1w.iloc[-2]['high'])
            pwl = float(df_1w.iloc[-2]['low'])

        # Detectar regímenes
        df_1d = self.regime_detector.detect_regime(df_1d)
        df_h4 = self.regime_detector.detect_regime(df_h4)
        df_h1 = self.regime_detector.detect_regime(df_h1)
        
        m1_regime = 'UNKNOWN'
        if not df_1m.empty:
            df_1m = self.regime_detector.detect_regime(df_1m)
            m1_regime = df_1m['market_regime'].iloc[-1]

        w1_regime = 'UNKNOWN'
        if not df_1w.empty:
            df_1w = self.regime_detector.detect_regime(df_1w)
            w1_regime = df_1w['market_regime'].iloc[-1]

        d1_regime = df_1d['market_regime'].iloc[-1]
        h4_regime = df_h4['market_regime'].iloc[-1]
        h1_regime = df_h1['market_regime'].iloc[-1]

        # Lógica de Sesgo Direccional (Top-Down)
        direction = 'NEUTRAL'
        strength = 0.5
        reason = "Contexto HTF indeciso o ruidoso."

        # BULLISH CONDITIONS (Guiado por D1 y 4H)
        if d1_regime == 'MARKUP':
            if h4_regime in ['MARKUP', 'ACCUMULATION', 'RANGING']:
                direction = 'BULLISH'
                strength = 1.0 if h4_regime == 'MARKUP' else 0.8
                reason = f"1D MARKUP + {h4_regime} en 4H. Fuerte sesgo institucional alcista."
            else:
                direction = 'BULLISH'
                strength = 0.6
                reason = "1D MARKUP pero 4H en corrección."
        
        # BEARISH CONDITIONS
        elif d1_regime == 'MARKDOWN':
            if h4_regime in ['MARKDOWN', 'DISTRIBUTION', 'RANGING']:
                direction = 'BEARISH'
                strength = 1.0 if h4_regime == 'MARKDOWN' else 0.8
                reason = f"1D MARKDOWN + {h4_regime} en 4H. Fuerte sesgo institucional bajista."
            else:
                direction = 'BEARISH'
                strength = 0.6
                reason = "1D MARKDOWN pero 4H en rebote."

        # TRANSITION / ACCUMULATION
        elif d1_regime == 'ACCUMULATION':
            if h4_regime in ['ACCUMULATION', 'MARKUP']:
                direction = 'BULLISH'
                strength = 0.7
                reason = "1D ACCUMULATION + 4H iniciando ciclo alcista."
            else:
                direction = 'NEUTRAL'
                strength = 0.4
                reason = "1D ACCUMULATION. Aún sin confirmación en 4H."

        elif d1_regime == 'DISTRIBUTION':
            if h4_regime in ['DISTRIBUTION', 'MARKDOWN']:
                direction = 'BEARISH'
                strength = 0.7
                reason = "1D DISTRIBUTION + 4H iniciando ciclo bajista."
            else:
                direction = 'NEUTRAL'
                strength = 0.4
                reason = "1D DISTRIBUTION. Aún sin confirmación en 4H."

        return HTFBias(
            direction=direction,
            strength=strength,
            reason=reason,
            m1_regime=m1_regime,
            w1_regime=w1_regime,
            d1_regime=d1_regime,
            h4_regime=h4_regime,
            h1_regime=h1_regime,
            pdh=pdh,
            pdl=pdl,
            pwh=pwh,
            pwl=pwl
        )
