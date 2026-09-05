from engine.core.logger import logger
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, classification_report
import os
from pathlib import Path
from typing import Dict, Any, Optional

# Importar nuestra fábrica de features
from engine.ml.features import FeatureEngineer

def train_slingshot_model(data_path: Path, model_dir: Path):
    """
    Entrena el Cerebro de Criptodamus (XGBoost) utilizando datos históricos.
    """
    logger.info("📈 Cargando datos desde el Data Lake...")
    if not data_path.exists():
        logger.error(f"Error: No se encontró la data en {data_path}")
        return
        
    df = pd.read_parquet(data_path)
    
    # 1. Feature Engineering
    logger.info("⚙️ Generando Features Estacionarias (Returns, Volatility, TA)...")
    engineer = FeatureEngineer(target_horizon=2) # Predecir a 2 velas vista
    ml_dataset = engineer.prepare_dataset(df, classification=True)
    
    # 2. Definir Features (X) y Target (y)
    # Excluimos variables "feas" para un árbol de decisión (como el Timestamp o el string del Símbolo)
    to_drop = ['timestamp', 'open', 'high', 'low', 'close', 'number_of_trades', 'TARGET']
    
    # Nos aseguramos de mantener solo variables numéricas predictivas
    feature_cols = [col for col in ml_dataset.columns if col not in to_drop and pd.api.types.is_numeric_dtype(ml_dataset[col])]
    
    X = ml_dataset[feature_cols]
    y = ml_dataset['TARGET']
    
    logger.info(f"📊 Dataset final: {X.shape[0]} muestras, {X.shape[1]} features.")
    
    # 3. Time-Series Split (No hacemos un split aleatorio porque filtraríamos el "futuro" al "pasado")
    # Entrenamiento: Primer 80% chronológicamente. Prueba: Último 20%
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    
    # 4. Configurar el Modelo XGBoost
    logger.info("🧠 Entrenando XGBoost Gradient Boosting Model...")
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
    logger.info("\n⚖️ Evaluando Precisión en Data No Vista (Test Set)...")
    preds = model.predict(X_test)
    acc = accuracy_score(y_test, preds)
    prec = precision_score(y_test, preds)
    
    logger.info(f"✅ Accuracy (Acierto General): {acc:.2%}")
    logger.info(f"🎯 Precision (Cuando dice COMPRA, cuántas veces acierta): {prec:.2%}")
    logger.info("\nReporte Detallado:")
    logger.info(classification_report(y_test, preds))
    
    # 7. Guardar el Modelo (Exportación Ultrarrápida JSON)
    os.makedirs(model_dir, exist_ok=True)
    model_path = model_dir / "slingshot_xgb_15m_v2.json"
    model.save_model(str(model_path))
    
    logger.info(f"💾 Modelo guardado exitosamente en: {model_path}")
    return {"accuracy": acc, "precision": prec, "model_path": str(model_path)}

def safe_auto_retrain(min_accuracy: float = 0.52) -> Dict[str, Any]:
    """
    [AUTO-RETRAIN PIPELINE v50.0 FAIL-SAFE]
    Entrena un modelo candidato y solo reemplaza el modelo de producción
    si supera el umbral mínimo de calidad en datos fuera de muestra (Out-Of-Sample).
    """
    base_dir = Path(__file__).parent.parent.parent
    data_file = base_dir / "engine" / "backtest" / "data" / "btcusdt_15m_1YEAR.parquet"
    if not data_file.exists():
        data_file = base_dir / "engine" / "backtest" / "data" / "BTCUSDT_15m_180d.parquet"
        
    models_dir = Path(__file__).parent / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    
    if not data_file.exists():
        logger.warning(f"⚠️ [AUTO-RETRAIN] Dataset histórico no encontrado en {data_file}. Omitiendo reentrenamiento.")
        return {"status": "skipped", "reason": "no_data"}
        
    try:
        df = pd.read_parquet(data_file)
        engineer = FeatureEngineer(target_horizon=2)
        ml_dataset = engineer.prepare_dataset(df.tail(15000), classification=True)
        
        to_drop = ['timestamp', 'open', 'high', 'low', 'close', 'number_of_trades', 'TARGET']
        feature_cols = [col for col in ml_dataset.columns if col not in to_drop and pd.api.types.is_numeric_dtype(ml_dataset[col])]
        
        X = ml_dataset[feature_cols]
        y = ml_dataset['TARGET']
        
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
        
        candidate_model = xgb.XGBClassifier(
            n_estimators=150,
            learning_rate=0.05,
            max_depth=5,
            subsample=0.8,
            colsample_bytree=0.8,
            eval_metric='logloss',
            random_state=42
        )
        candidate_model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
        
        preds = candidate_model.predict(X_test)
        cand_acc = float(accuracy_score(y_test, preds))
        cand_prec = float(precision_score(y_test, preds, zero_division=0))
        
        logger.info(f"🧪 [AUTO-RETRAIN] Candidato evaluado: Accuracy {cand_acc:.2%}, Precision {cand_prec:.2%}")
        
        if cand_acc >= min_accuracy:
            target_file = models_dir / "slingshot_xgb_15m_v2.json"
            temp_file = models_dir / "candidate_xgb.json"
            candidate_model.save_model(str(temp_file))
            # Reemplazo atómico seguro
            import shutil
            shutil.move(str(temp_file), str(target_file))
            logger.info(f"🏆 [AUTO-RETRAIN] Modelo promovido a producción con {cand_acc:.2%} de Accuracy.")
            return {"status": "promoted", "accuracy": cand_acc, "precision": cand_prec}
        else:
            logger.warning(f"🛡️ [AUTO-RETRAIN FAIL-SAFE] Candidato rechazado por bajo rendimiento ({cand_acc:.2%} < {min_accuracy:.2%}). Se preserva modelo actual.")
            return {"status": "rejected", "accuracy": cand_acc, "min_required": min_accuracy}
            
    except Exception as retrain_err:
        logger.error(f"❌ [AUTO-RETRAIN] Error durante ciclo de reentrenamiento: {retrain_err}")
        return {"status": "error", "message": str(retrain_err)}

if __name__ == "__main__":
    # Rutas relativas al proyecto
    base_dir = Path(__file__).parent.parent.parent
    data_file = base_dir / "engine" / "backtest" / "data" / "btcusdt_15m_1YEAR.parquet"
    if not data_file.exists():
        data_file = base_dir / "data" / "btcusdt_15m_1YEAR.parquet"
    models_out = base_dir / "engine" / "ml" / "models"
    
    train_slingshot_model(data_file, models_out)
