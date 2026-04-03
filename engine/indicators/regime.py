from engine.core.logger import logger
import pandas as pd
import numpy as np

class RegimeDetector:
    """
    Capa 2: Detector de Régimen de Mercado SMC.
    Clasifica el estado del mercado basándose puramente en ACCIÓN DE PRECIO (Price Action),
    sin usar indicadores retail como Medias Móviles o Bollinger Bands.
    
    Regímenes:
    1. EXPANSION_BULL (Markup): HH/HL + Momentum
    2. EXPANSION_BEAR (Markdown): LH/LL + Momentum
    3. ACCUMULATION: Rango en zona de descuento (Suelo)
    4. DISTRIBUTION: Rango en zona premium (Techo)
    5. CONSOLIDATION: Rango lateral sin sesgo claro
    6. CHOPPY: Alta volatilidad sin dirección estructural
    """
    
    def __init__(self, structure_window: int = 50, consolidation_threshold: float = 0.15):
        self.window = structure_window
        self.threshold = consolidation_threshold
        
    def _calculate_action_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        # 1. Estructura de Mercado (Puntos Pivot/Fractales)
        df['rolling_high'] = df['high'].rolling(window=self.window).max()
        df['rolling_low'] = df['low'].rolling(window=self.window).min()
        
        # 2. Rango de Proporción (Premium vs Discount)
        # Posición del precio actual dentro del rango de los últimos 'self.window' periodos
        range_size = df['rolling_high'] - df['rolling_low']
        df['price_pos_pct'] = (df['close'] - df['rolling_low']) / range_size
        
        # 3. Volatilidad Estructural (ATR Relativo)
        # Usamos el rango verdadero para medir la "expansión" de las velas
        df['tr'] = np.maximum(df['high'] - df['low'], 
                             np.maximum(abs(df['high'] - df['close'].shift(1)), 
                                      abs(df['low'] - df['close'].shift(1))))
        df['atr'] = df['tr'].rolling(window=20).mean()
        df['atr_mean'] = df['atr'].rolling(window=100).mean()
        
        # Coeficiente de Expansión: Si es > 1.2, el mercado está expandiendo con fuerza
        df['expansion_ratio'] = df['atr'] / df['atr_mean']
        
        # 4. Momentum Estructural (Delta de Cierres)
        df['momentum'] = df['close'].diff(5)
        
        return df

    def detect_regime(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Aplica reglas de Price Action para el etiquetado de régimen institucional.
        """
        df = self._calculate_action_metrics(df)
        df['market_regime'] = 'UNKNOWN'
        
        # Definición de Estados Base
        is_uptrend = (df['close'] > df['close'].shift(self.window // 2)) & (df['momentum'] > 0)
        is_downtrend = (df['close'] < df['close'].shift(self.window // 2)) & (df['momentum'] < 0)
        
        # Consolidación: Rango estrecho (volatilidad baja vs el promedio histórico)
        is_low_vol = df['expansion_ratio'] < 0.85
        
        # Proximidad a extremos (Premium/Discount)
        is_premium = df['price_pos_pct'] > 0.75
        is_discount = df['price_pos_pct'] < 0.25
        
        # --- LÓGICA DE ASIGNACIÓN SMC ---
        
        # 1. MARKUP (Expansión Alcista)
        mask_markup = is_uptrend & ~is_low_vol
        df.loc[mask_markup, 'market_regime'] = 'MARKUP'
        
        # 2. MARKDOWN (Expansión Bajista)
        mask_markdown = is_downtrend & ~is_low_vol
        df.loc[mask_markdown, 'market_regime'] = 'MARKDOWN'
        
        # 3. ACUMULACIÓN (Smart Money comprando en descuento)
        mask_accum = is_low_vol & is_discount
        df.loc[mask_accum, 'market_regime'] = 'ACCUMULATION'
        
        # 4. DISTRIBUCIÓN (Smart Money vendiendo en premium)
        mask_distrib = is_low_vol & is_premium
        df.loc[mask_distrib, 'market_regime'] = 'DISTRIBUTION'
        
        # 5. RANGING (Consolidación en zona media / Re-acumulación)
        mask_ranging = is_low_vol & (~is_premium & ~is_discount)
        df.loc[mask_ranging, 'market_regime'] = 'RANGING'
        
        # 6. CHOPPY (Indecisión / Whipsaws)
        mask_choppy = ~is_low_vol & ~is_uptrend & ~is_downtrend
        df.loc[mask_choppy, 'market_regime'] = 'CHOPPY'
        
        # Mapeo final para compatibilidad con el resto del sistema (Wyckoff Names)
        # Esto asegura que el Frontend no explote al buscar 'MARKUP' o 'ACCUMULATION'
        df['market_regime'] = df['market_regime'].replace('UNKNOWN', 'RANGING')
        
        return df

if __name__ == "__main__":
    # Test rápido de estructura
    test_df = pd.DataFrame({
        'close': [100 + i + (np.random.randn() * 2) for i in range(200)],
        'high':  [105 + i for i in range(200)],
        'low':   [95 + i for i in range(200)]
    })
    test_df['timestamp'] = pd.date_range(start='2024-01-01', periods=200, freq='15T')
    
    detector = RegimeDetector()
    results = detector.detect_regime(test_df)
    logger.info("Regímenes detectados (SMC Pure Price Action):")
    logger.info(results['market_regime'].value_counts())
