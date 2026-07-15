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

    def to_dict(self):
        from dataclasses import asdict
        return asdict(self)

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

        # ⚙️ Mapeo cuantitativo de regímenes (Markup=+1.0, Accumulation=+0.5, Markdown=-1.0, Distribution=-0.5, Ranging=0.0)
        regime_scores = {
            'MARKUP': 1.0,
            'ACCUMULATION': 0.5,
            'RANGING': 0.0,
            'DISTRIBUTION': -0.5,
            'MARKDOWN': -1.0,
            'UNKNOWN': 0.0
        }

        # ⚖️ Ponderación de grado institucional
        weights = {
            'M1': 0.15,
            'W1': 0.25,
            'D1': 0.30,
            'H4': 0.20,
            'H1': 0.10
        }

        # Calcular score direccional ponderado
        score = 0.0
        score += regime_scores.get(m1_regime, 0.0) * weights['M1']
        score += regime_scores.get(w1_regime, 0.0) * weights['W1']
        score += regime_scores.get(d1_regime, 0.0) * weights['D1']
        score += regime_scores.get(h4_regime, 0.0) * weights['H4']
        score += regime_scores.get(h1_regime, 0.0) * weights['H1']

        # Determinar dirección, fuerza y justificación basada en el score consolidado
        if score > 0.25:
            direction = 'BULLISH'
            strength = min(1.0, float(abs(score) / 0.8)) # Normalizar fuerza
            reason = f"Sesgo institucional ALCISTA multifractal (Score: {score:+.2f}). M1={m1_regime}, W1={w1_regime}, D1={d1_regime}, H4={h4_regime}, H1={h1_regime}."
        elif score < -0.25:
            direction = 'BEARISH'
            strength = min(1.0, float(abs(score) / 0.8))
            reason = f"Sesgo institucional BAJISTA multifractal (Score: {score:+.2f}). M1={m1_regime}, W1={w1_regime}, D1={d1_regime}, H4={h4_regime}, H1={h1_regime}."
        else:
            direction = 'NEUTRAL'
            strength = float(abs(score) / 0.25)
            reason = f"Consolidación o conflicto de sesgo macro (Score: {score:+.2f}). M1={m1_regime}, W1={w1_regime}, D1={d1_regime}, H4={h4_regime}, H1={h1_regime}."

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
