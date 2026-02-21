import pandas as pd
import numpy as np

# Importar indicadores base de nuestro propio motor para no duplicar lógica
from engine.indicators.momentum import apply_criptodamus_suite

class FeatureEngineer:
    """
    Capa 3B (Machine Learning - Step 1).
    Transforma datos crudos (OHLCV) en 'Features' (Variables predictivas) 
    para alimentar al modelo XGBoost/LightGBM.
    """
    
    def __init__(self, target_horizon: int = 1):
        """
        :param target_horizon: Cuántas velas hacia el futuro queremos predecir (ej: 1 vela = 15m)
        """
        self.target_horizon = target_horizon
        
    def generate_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Construye un dataset rico en features estacionarias.
        (Evitamos pasar precios crudos al ML porque no son estacionarios, 
        pasamos RETORNOS y DISTANCIAS).
        """
        df = df.copy()
        
        # 1. Inyectar suite base de TA (RSI, MACD, BBWP)
        df = apply_criptodamus_suite(df)
        
        # 2. Features de Retorno (Velocidad del precio)
        # Retorno logarítmico (mejor para ML financiero)
        df['return_1'] = np.log(df['close'] / df['close'].shift(1))
        df['return_3'] = np.log(df['close'] / df['close'].shift(3))
        df['return_5'] = np.log(df['close'] / df['close'].shift(5))
        
        # 3. Features de Volatilidad (ATR simplificado y Rollings)
        df['high_low_spread'] = (df['high'] - df['low']) / df['open']
        df['volatility_10'] = df['return_1'].rolling(window=10).std()
        df['volatility_20'] = df['return_1'].rolling(window=20).std()
        
        # 4. Features de Distancia (Media Reversión Cues)
        # ¿Qué tan lejos estamos de las EMAs clave?
        df['ema_21'] = df['close'].ewm(span=21, adjust=False).mean()
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        
        df['dist_ema21'] = (df['close'] - df['ema_21']) / df['ema_21']
        df['dist_ema50'] = (df['close'] - df['ema_50']) / df['ema_50']
        
        # 5. Features Categóricas / Temporales (Ciclicidad)
        # Ayuda al árbol de decisión a saber "A qué hora estamos"
        if pd.api.types.is_datetime64_any_dtype(df['timestamp']):
             df['hour_sin'] = np.sin(2 * np.pi * df['timestamp'].dt.hour / 24.0)
             df['hour_cos'] = np.cos(2 * np.pi * df['timestamp'].dt.hour / 24.0)
             df['day_of_week'] = df['timestamp'].dt.dayofweek
             
        # Limpieza: Descartar valores NaN generados por los rolling windows
        df = df.dropna()
        
        return df
        
    def create_labels(self, df: pd.DataFrame, classification: bool = True) -> pd.DataFrame:
        """
        Crea la variable 'Y' (Objetivo) que el modelo intentará adivinar.
        """
        df = df.copy()
        
        # Calcular el retorno futuro (Precio en t+horizon / Precio actual)
        # Shift negativo trae datos del "futuro" a la fila actual
        future_return = (df['close'].shift(-self.target_horizon) - df['close']) / df['close']
        
        if classification:
            # 1 = Sube (Ganancia > 0.05%), 0 = Rango/Cae
            # Usamos un pequeño threshold (0.0005 = 0.05%) para evitar considerar ruido como tendencia alcista
            df['TARGET'] = (future_return > 0.0005).astype(int)
        else:
            # Regresión: predecir el % de retorno exacto
            df['TARGET'] = future_return
            
        # Al calcular el futuro, las últimas 'target_horizon' velas quedarán con NaN en el TARGET
        # porque aún no conocemos el futuro real de hoy.
        df = df.dropna(subset=['TARGET'])
        
        return df

    def prepare_dataset(self, df: pd.DataFrame, classification: bool = True) -> pd.DataFrame:
        """Ejecuta el pipeline completo de ingeniería de variables."""
        df_features = self.generate_features(df)
        df_final = self.create_labels(df_features, classification=classification)
        return df_final

if __name__ == "__main__":
    from pathlib import Path
    
    file_path = Path(__file__).parent.parent.parent / "data" / "btcusdt_15m.parquet"
    if file_path.exists():
        data = pd.read_parquet(file_path)
        
        engineer = FeatureEngineer(target_horizon=2) # Predecir a 30 min vista (2 velas de 15m)
        ml_dataset = engineer.prepare_dataset(data)
        
        print("🧠 Módulo Feature Engineering (Preparación para XGBoost)")
        print(f"Dimensiones Originales: {data.shape}")
        print(f"Dimensiones Transformadas: {ml_dataset.shape}")
        print(f"Features inyectadas: {[col for col in ml_dataset.columns if col not in data.columns]}")
        
        bullish_samples = ml_dataset[ml_dataset['TARGET'] == 1]
        print(f"\nBalance del Dataset:")
        print(f"Casos Alcistas (TARGET=1): {len(bullish_samples)}")
        print(f"Casos Bajistas/Rango (TARGET=0): {len(ml_dataset) - len(bullish_samples)}")
        print(ml_dataset.iloc[-1][['timestamp', 'close', 'return_1', 'rsi', 'dist_ema50', 'TARGET']])
