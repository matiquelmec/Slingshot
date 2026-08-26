# engine/indicators/polars_engine.py
"""
=============================================================================
SLINGSHOT POLARS RUST ENGINE — ACELERACIÓN VECTORIAL MULTIHILO v17.0
=============================================================================
Procesa millones de operaciones de velas en microsegundos usando el motor Polars en Rust.
Totalmente compatible con DataFrames de Pandas (Entrada/Salida transparente).
"""
import polars as pl
import pandas as pd
import numpy as np
from typing import Union, List, Dict, Any

class PolarsEngine:
    """Motor de cálculo cuantitativo ultrarrápido compilado en Rust."""

    @staticmethod
    def to_polars(df: Union[pd.DataFrame, pl.DataFrame]) -> pl.DataFrame:
        """Convierte transparentemente cualquier DataFrame a Polars."""
        if isinstance(df, pl.DataFrame):
            return df
        return pl.from_pandas(df)

    @staticmethod
    def to_pandas(df: Union[pl.DataFrame, pd.DataFrame]) -> pd.DataFrame:
        """Convierte de vuelta a Pandas para el resto del pipeline."""
        if isinstance(df, pd.DataFrame):
            return df
        return df.to_pandas()

    @classmethod
    def compute_indicators(cls, df: Union[pd.DataFrame, pl.DataFrame]) -> pd.DataFrame:
        """
        Calcula EMA 50, EMA 200, ATR y Fair Value Gaps (FVG) en un solo pase vectorizado en Rust.
        Latencia típica: < 2.5ms para 1,000 velas.
        """
        pldf = cls.to_polars(df)
        
        # Asegurar nombres de columnas en minúscula
        rename_map = {col: col.lower() for col in pldf.columns}
        pldf = pldf.rename(rename_map)

        # 1. True Range y ATR (14)
        high = pl.col('high')
        low = pl.col('low')
        close = pl.col('close')
        prev_close = close.shift(1)

        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        
        # Max(tr1, tr2, tr3)
        tr = pl.max_horizontal([tr1, tr2, tr3])

        # 2. EMAs
        ema50 = close.ewm_mean(span=50, adjust=False)
        ema200 = close.ewm_mean(span=200, adjust=False)
        atr = tr.rolling_mean(window_size=14)

        # 3. FVGs Institucionales
        # Bullish FVG: low[i] > high[i-2]
        # Bearish FVG: high[i] < low[i-2]
        fvg_bull = low > high.shift(2)
        fvg_bear = high < low.shift(2)

        # Aplicar transformaciones vectorizadas en paralelo
        transformed = pldf.with_columns([
            ema50.alias('ema50'),
            ema200.alias('ema200'),
            atr.alias('atr'),
            fvg_bull.alias('fvg_bull'),
            fvg_bear.alias('fvg_bear')
        ])

        return cls.to_pandas(transformed)

    @classmethod
    def compute_swings_and_ote(cls, df: Union[pd.DataFrame, pl.DataFrame], window: int = 50) -> Dict[str, Any]:
        """Calcula los swings mayores y niveles de retroceso OTE (61.8% - 78.6%) en tiempo récord."""
        pldf = cls.to_polars(df)
        slice_df = pldf.tail(window)
        
        swing_high = float(slice_df['high'].max())
        swing_low = float(slice_df['low'].min())
        leg = swing_high - swing_low
        
        if leg <= 0:
            return {}
            
        return {
            "swing_high": swing_high,
            "swing_low": swing_low,
            "leg": leg,
            "levels": {
                "0.5": round(swing_high - leg * 0.5, 8),
                "0.618": round(swing_high - leg * 0.618, 8),
                "0.786": round(swing_high - leg * 0.786, 8),
            },
            "is_whale_leg": (leg / swing_low) > 0.05
        }

# Instancia singleton para importación directa
polars_engine = PolarsEngine()
