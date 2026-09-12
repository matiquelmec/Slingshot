from engine.core.logger import logger
import pandas as pd
import numpy as np

class TripleBarrierLabeler:
    """
    [LÓPEZ DE PRADO TRIPLE BARRIER METHOD]
    Etiquetado Cuantitativo Institucional:
    - Barrera Superior: +pt_mult * ATR (Take Profit Asimétrico)
    - Barrera Inferior: -sl_mult * ATR (Stop Loss Estructural)
    - Barrera Vertical: max_holding_bars (Tiempo Límite)
    
    Target:
      1: Toca Take Profit antes que Stop Loss
      0: Toca Stop Loss o expira sin alcanzar rentabilidad
    """
    def __init__(self, pt_mult: float = 2.0, sl_mult: float = 1.0, max_holding_bars: int = 16):
        self.pt_mult = pt_mult
        self.sl_mult = sl_mult
        self.max_holding_bars = max_holding_bars

    def compute_barriers(self, df: pd.DataFrame, direction: str = "LONG") -> pd.Series:
        n = len(df)
        labels = np.full(n, np.nan)
        
        # Calcular o recuperar ATR
        if 'atr' not in df.columns:
            high_low = df['high'] - df['low']
            high_close = (df['high'] - df['close'].shift(1)).abs()
            low_close = (df['low'] - df['close'].shift(1)).abs()
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            atr = tr.rolling(14).mean().fillna(df['close'] * 0.005)
        else:
            atr = df['atr'].fillna(df['close'] * 0.005)

        highs = df['high'].values
        lows = df['low'].values
        closes = df['close'].values
        atr_vals = atr.values

        for i in range(n - self.max_holding_bars):
            entry_p = closes[i]
            vol = atr_vals[i]
            if vol <= 0 or np.isnan(vol):
                vol = entry_p * 0.005

            if direction == "LONG":
                pt_price = entry_p + self.pt_mult * vol
                sl_price = entry_p - self.sl_mult * vol

                outcome = 0
                for h in range(1, self.max_holding_bars + 1):
                    fut = i + h
                    if lows[fut] <= sl_price:
                        outcome = 0
                        break
                    if highs[fut] >= pt_price:
                        outcome = 1
                        break
                else:
                    final_close = closes[i + self.max_holding_bars]
                    outcome = 1 if (final_close - entry_p) > (0.5 * vol) else 0

                labels[i] = outcome
            else:
                pt_price = entry_p - self.pt_mult * vol
                sl_price = entry_p + self.sl_mult * vol

                outcome = 0
                for h in range(1, self.max_holding_bars + 1):
                    fut = i + h
                    if highs[fut] >= sl_price:
                        outcome = 0
                        break
                    if lows[fut] <= pt_price:
                        outcome = 1
                        break
                else:
                    final_close = closes[i + self.max_holding_bars]
                    outcome = 1 if (entry_p - final_close) > (0.5 * vol) else 0

                labels[i] = outcome

        return pd.Series(labels, index=df.index)


class FeatureEngineer:
    """
    Capa 3B (Machine Learning - Step 1).
    Transforma datos crudos (OHLCV) en 'SMC Features' (Variables predictivas institucionales) 
    para alimentar al modelo XGBoost/LightGBM.
    """
    
    def __init__(self, target_horizon: int = 1):
        self.target_horizon = target_horizon
        
    def generate_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Construye un dataset basado exclusivamente en Price Action Institucional.
        """
        df = df.copy()
        
        # 1. Inyectar Smart Money Concepts (El "Cerebro" Institucional)
        from engine.indicators.structure import identify_order_blocks
        df = identify_order_blocks(df)
        
        # Convertimos booleanos de SMC a numéricos (1/0)
        for col in ['ob_bullish', 'ob_bearish', 'fvg_bullish', 'fvg_bearish']:
            if col in df.columns:
                df[col] = df[col].astype(int)
        
        # 2. Features de Tiempo desde el último bloque (Decay)
        def time_since_last(series):
            return series.groupby(series.cumsum()).cumcount()
        
        if 'ob_bullish' in df.columns:
            df['bars_since_bull_ob'] = time_since_last(df['ob_bullish']).replace(0, np.nan).ffill().fillna(100)
        if 'ob_bearish' in df.columns:
            df['bars_since_bear_ob'] = time_since_last(df['ob_bearish']).replace(0, np.nan).ffill().fillna(100)
            
        # 3. Features de Retorno e Intensidad (RVOL)
        df['return_1'] = np.log(df['close'] / df['close'].shift(1))
        df['return_5'] = np.log(df['close'] / df['close'].shift(5))
        
        # Inyectar RVOL si está disponible
        from engine.indicators.volume import confirm_trigger
        df = confirm_trigger(df)
        if 'rvol' in df.columns:
            df['rvol_feature'] = df['rvol'].fillna(1.0)
        
        # 4. Estructura de Mercado (Distancia a extremos del rango)
        window = 50
        df['rolling_high'] = df['high'].rolling(window=window).max()
        df['rolling_low'] = df['low'].rolling(window=window).min()
        df['range_pos_pct'] = (df['close'] - df['rolling_low']) / (df['rolling_high'] - df['rolling_low'])
        
        # 5. Features de Sesión (KillZone binary)
        from engine.core.session_manager import TimeFilter
        tf = TimeFilter()
        df['is_killzone'] = df['timestamp'].apply(lambda x: 1 if tf.is_killzone(x) else 0).fillna(0).astype(int)
        
        # 6. Features Temporales
        if pd.api.types.is_datetime64_any_dtype(df['timestamp']):
             df['hour_sin'] = np.sin(2 * np.pi * df['timestamp'].dt.hour / 24.0)
             df['hour_cos'] = np.cos(2 * np.pi * df['timestamp'].dt.hour / 24.0)
             
        # Limpieza final de NaN
        df = df.dropna()
        return df

    def create_labels(self, df: pd.DataFrame, classification: bool = True, method: str = "triple_barrier") -> pd.DataFrame:
        df = df.copy()
        if method == "triple_barrier":
            labeler = TripleBarrierLabeler(pt_mult=2.0, sl_mult=1.0, max_holding_bars=16)
            df['TARGET'] = labeler.compute_barriers(df, direction="LONG")
        else:
            future_return = (df['close'].shift(-self.target_horizon) - df['close']) / df['close']
            if classification:
                df['TARGET'] = (future_return > 0.0005).astype(int)
            else:
                df['TARGET'] = future_return
            
        df = df.dropna(subset=['TARGET'])
        df['TARGET'] = df['TARGET'].astype(int)
        return df

    def prepare_dataset(self, df: pd.DataFrame, classification: bool = True, method: str = "triple_barrier") -> pd.DataFrame:
        df_features = self.generate_features(df)
        df_final = self.create_labels(df_features, classification=classification, method=method)
        return df_final

if __name__ == "__main__":
    logger.info("🧠 Feature Engineering SMC Purificado.")
