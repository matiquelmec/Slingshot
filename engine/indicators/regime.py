import pandas as pd
import numpy as np

class RegimeDetector:
    """
    Capa 2: Router Híbrido (Detector de Régimen de Flujo).
    Clasifica matemáticamente el estado actual del mercado basándose en las fases de Wyckoff:
    1. Acumulación (Rango en Suelo)
    2. Markup (Tendencia Alcista)
    3. Distribución (Rango en Techo)
    4. Markdown (Tendencia Bajista)
    """
    
    def __init__(self, slow_sma: int = 200, fast_sma: int = 50, bb_period: int = 20, bb_std: float = 2.0):
        self.slow_sma = slow_sma
        self.fast_sma = fast_sma
        self.bb_period = bb_period
        self.bb_std = bb_std
        
    def _calculate_base_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        # Medias Móviles para detectar Dirección de Tendencia (Trend Alignment)
        df['sma_fast'] = df['close'].rolling(window=self.fast_sma).mean()
        df['sma_slow'] = df['close'].rolling(window=self.slow_sma).mean()
        
        # Calcular pendiente (Slope) de la SMA lenta (para ver si la tendencia macro es fuerte)
        # Usamos una ventana de 10 periodos para ver la inclinación
        df['sma_slow_slope'] = df['sma_slow'].diff(10)
        
        # Bollinger Bands para Volatilidad / Rango (Squeeze)
        sma_bb = df['close'].rolling(window=self.bb_period).mean()
        std_bb = df['close'].rolling(window=self.bb_period).std()
        df['bb_upper'] = sma_bb + (std_bb * self.bb_std)
        df['bb_lower'] = sma_bb - (std_bb * self.bb_std)
        
        # Ancho de las bandas (Volatilidad). Si es bajo, estamos en Consolidación (Acumulación/Distribución)
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / sma_bb
        
        # Promedio del ancho de bandas para saber qué es "Alta" o "Baja" volatilidad
        df['bb_width_mean'] = df['bb_width'].rolling(window=self.slow_sma).mean()
        
        # Distancia del precio a la SMA 200 (Para determinar si estamos en Suelo o Techo estadístico)
        df['dist_to_sma200'] = (df['close'] - df['sma_slow']) / df['sma_slow']
        
        return df

    def detect_regime(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Aplica las reglas lógicas para etiquetar cada vela con su Régimen de Mercado.
        Las máscaras se aplican en orden de PRIORIDAD DESCENDENTE con exclusión mutua.
        """
        df = self._calculate_base_metrics(df)
        
        # Inicializar columna
        df['market_regime'] = 'UNKNOWN'
        
        # Condiciones base
        is_uptrend = (df['sma_fast'] > df['sma_slow']) & (df['sma_slow_slope'] > 0)
        is_downtrend = (df['sma_fast'] < df['sma_slow']) & (df['sma_slow_slope'] < 0)
        
        # Volatilidad baja = Consolidación (Rango)
        is_consolidation = df['bb_width'] < (df['bb_width_mean'] * 0.8) # 20% menos volatilidad que el promedio
        
        # Precio sobre extendido = Techo. Precio muy por debajo = Suelo.
        is_high_price = df['dist_to_sma200'] > 0.03
        is_low_price = df['dist_to_sma200'] < -0.03
        
        # --- Lógica WYCKOFF con PRIORIDAD EXPLÍCITA (sin conflictos de sobreescritura) ---
        # El orden importa: las tendencias claras tienen prioridad sobre la consolidación,
        # y dentro de consolidación, las zonas extremas (ACCUM/DIST) tienen prioridad sobre RANGING.
        
        # 1. MARKUP: Tendencia Alcista Clara + Expansión de Volatilidad (prioridad alta)
        mask_markup = is_uptrend & ~is_consolidation
        df.loc[mask_markup, 'market_regime'] = 'MARKUP'
        
        # 2. MARKDOWN: Tendencia Bajista Clara + Expansión de Volatilidad (prioridad alta)
        mask_markdown = is_downtrend & ~is_consolidation
        df.loc[mask_markdown, 'market_regime'] = 'MARKDOWN'
        
        # 3. ACUMULACIÓN: Rango + Precio Bajo (excluye regímenes de tendencia ya asignados)
        # BUG FIX: Usar ~mask_markup & ~mask_markdown para exclusión mutua explícita
        mask_accum = is_consolidation & is_low_price & ~mask_markup & ~mask_markdown
        df.loc[mask_accum, 'market_regime'] = 'ACCUMULATION'
        
        # 4. DISTRIBUCIÓN: Rango + Precio Alto (excluye todo lo anterior)
        mask_distrib = is_consolidation & is_high_price & ~mask_markup & ~mask_markdown & ~mask_accum
        df.loc[mask_distrib, 'market_regime'] = 'DISTRIBUTION'
        
        # 5. RANGING: Consolidación media sin extensión extrema (lo que sobra)
        mask_ranging = is_consolidation & ~mask_markup & ~mask_markdown & ~mask_accum & ~mask_distrib
        df.loc[mask_ranging, 'market_regime'] = 'RANGING'
        
        return df


if __name__ == "__main__":
    import os
    from pathlib import Path
    
    file_path = Path(__file__).parent.parent.parent / "data" / "btcusdt_15m.parquet"
    if os.path.exists(file_path):
        data = pd.read_parquet(file_path)
        
        detector = RegimeDetector()
        analyzed_data = detector.detect_regime(data)
        
        # Remover las "UNKNOWN" iniciales (por falta de datos para la SMA 200)
        valid_data = analyzed_data.dropna(subset=['market_regime'])
        valid_data = valid_data[valid_data['market_regime'] != 'UNKNOWN']
        
        # Contar cuántas velas pasaron en cada régimen
        regime_counts = valid_data['market_regime'].value_counts()
        
        print("🧠 Router Capa 2: Detector de Régimen de Mercado (Wyckoff)")
        print(f"Total de velas analizadas (post-calentamiento medias móviles): {len(valid_data)}\n")
        
        print(f"📊 Frecuencia de Fases en BTCUSDT (15m):")
        for regime, count in regime_counts.items():
            percentage = (count / len(valid_data)) * 100
            if regime == "MARKUP": icon = "🚀"
            elif regime == "MARKDOWN": icon = "🩸"
            elif regime == "ACCUMULATION": icon = "🔋"
            elif regime == "DISTRIBUTION": icon = "⚠️"
            else: icon = "❓"
            
            print(f"{icon} {regime.ljust(15)}: {count} velas ({percentage:.1f}%)")
            
        print("\n⚙️ Logística de Ruteo (SLINGSHOT Action):")
        print("- Si es ACCUMULATION -> Enrutar a MeanReversion (Long)")
        print("- Si es MARKUP       -> Enrutar a TrendFollowing / SMC Continuation")
        print("- Si es DISTRIBUTION -> Enrutar a SMC Failed Auction (Cacería Liquidez Techo)")
        print("- Si es MARKDOWN     -> Enrutar a QuantVolatility Short")
    else:
        print("Data file not found.")
