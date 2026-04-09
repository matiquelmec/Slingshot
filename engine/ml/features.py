from engine.core.logger import logger
import pandas as pd
import numpy as np

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
        
    def create_labels(self, df: pd.DataFrame, classification: bool = True) -> pd.DataFrame:
        df = df.copy()
        future_return = (df['close'].shift(-self.target_horizon) - df['close']) / df['close']
        
        if classification:
            df['TARGET'] = (future_return > 0.0005).astype(int)
        else:
            df['TARGET'] = future_return
            
        df = df.dropna(subset=['TARGET'])
        return df

    def prepare_dataset(self, df: pd.DataFrame, classification: bool = True) -> pd.DataFrame:
        df_features = self.generate_features(df)
        df_final = self.create_labels(df_features, classification=classification)
        return df_final

if __name__ == "__main__":
    logger.info("🧠 Feature Engineering SMC Purificado.")
