import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, classification_report
import os
from pathlib import Path

# Importar nuestra fábrica de features
from engine.ml.features import FeatureEngineer

def train_slingshot_model(data_path: Path, model_dir: Path):
    """
    Entrena el Cerebro de Criptodamus (XGBoost) utilizando datos históricos.
    """
    print("📈 Cargando datos desde el Data Lake...")
    if not data_path.exists():
        print(f"Error: No se encontró la data en {data_path}")
        return
        
    df = pd.read_parquet(data_path)
    
    # 1. Feature Engineering
    print("⚙️ Generando Features Estacionarias (Returns, Volatility, TA)...")
    engineer = FeatureEngineer(target_horizon=2) # Predecir a 2 velas vista
    ml_dataset = engineer.prepare_dataset(df, classification=True)
    
    # 2. Definir Features (X) y Target (y)
    # Excluimos variables "feas" para un árbol de decisión (como el Timestamp o el string del Símbolo)
    to_drop = ['timestamp', 'open', 'high', 'low', 'close', 'number_of_trades', 'TARGET']
    
    # Nos aseguramos de mantener solo variables numéricas predictivas
    feature_cols = [col for col in ml_dataset.columns if col not in to_drop and pd.api.types.is_numeric_dtype(ml_dataset[col])]
    
    X = ml_dataset[feature_cols]
    y = ml_dataset['TARGET']
    
    print(f"📊 Dataset final: {X.shape[0]} muestras, {X.shape[1]} features.")
    
    # 3. Time-Series Split (No hacemos un split aleatorio porque filtraríamos el "futuro" al "pasado")
    # Entrenamiento: Primer 80% chronológicamente. Prueba: Último 20%
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    
    # 4. Configurar el Modelo XGBoost
    print("🧠 Entrenando XGBoost Gradient Boosting Model...")
    model = xgb.XGBClassifier(
        n_estimators=300,        # Número de árboles
        learning_rate=0.05,      # Cuánto aprende de los errores pasados
        max_depth=6,             # Profundidad de cada árbol (evitar overfitting)
        subsample=0.8,           # Usar el 80% de los datos por árbol
        colsample_bytree=0.8,    # Usar el 80% de las features por árbol
        eval_metric='logloss',
        use_label_encoder=False,
        random_state=42
    )
    
    # 5. Entrenar
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=50 # Imprimir progreso cada 50 árboles
    )
    
    # 6. Evaluar
    print("\n⚖️ Evaluando Precisión en Data No Vista (Test Set)...")
    preds = model.predict(X_test)
    acc = accuracy_score(y_test, preds)
    prec = precision_score(y_test, preds)
    
    print(f"✅ Accuracy (Acierto General): {acc:.2%}")
    print(f"🎯 Precision (Cuando dice COMPRA, cuántas veces acierta): {prec:.2%}")
    print("\nReporte Detallado:")
    print(classification_report(y_test, preds))
    
    # 7. Guardar el Modelo (Exportación Ultrarrápida JSON)
    os.makedirs(model_dir, exist_ok=True)
    model_path = model_dir / "slingshot_xgb_15m_v2.json"
    model.save_model(str(model_path))
    
    print(f"💾 Modelo guardado exitosamente en: {model_path}")
    
if __name__ == "__main__":
    # Rutas relativas al proyecto
    base_dir = Path(__file__).parent.parent.parent
    data_file = base_dir / "data" / "btcusdt_15m_1YEAR.parquet"
    models_out = base_dir / "engine" / "ml" / "models"
    
    train_slingshot_model(data_file, models_out)
