"""
engine/ml/train_rolling.py — SOP-75 Continuous Walk-Forward Rolling Trainer against SQLite WAL
=============================================================================================
Pipeline de reentrenamiento continuo que extrae las últimas N semanas de velas reales
desde la base de datos de producción (SQLite WAL o archivos de sincronización Bitunix/MT5),
ejecuta validación cruzada temporal libre de fuga de datos (Walk-Forward) y actualiza
el modelo XGBoost en producción de forma atómica con recarga en caliente (Hot-Reload).
"""

import os
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import accuracy_score, precision_score

from engine.core.logger import logger
from engine.ml.features import FeatureEngineer


class RollingWalkForwardTrainer:
    """
    Entrenador rodante Walk-Forward con soporte para SQLite WAL y fallback a Data Lake.
    """

    def __init__(
        self,
        target_horizon: int = 2,
        min_accuracy: float = 0.52,
        window_candles: int = 12000,  # ~125 días en 15m
        n_splits: int = 4,
    ):
        self.target_horizon = target_horizon
        self.min_accuracy = min_accuracy
        self.window_candles = window_candles
        self.n_splits = n_splits
        self.engineer = FeatureEngineer(target_horizon=target_horizon)

    def load_recent_candles_from_sqlite(self, db_path: Optional[Path] = None, symbol: str = "BTCUSDT") -> Optional[pd.DataFrame]:
        """
        Intenta cargar las velas más recientes almacenadas en la base de datos de producción.
        """
        candidate_paths = [
            db_path,
            Path(r"C:\Slingshot\data\slingshot.db"),
            Path(__file__).parent.parent.parent / "data" / "slingshot_vault.db",
            Path(__file__).parent.parent.parent / "data" / "market_data.db"
        ]

        valid_path = None
        for p in candidate_paths:
            if p and Path(p).exists():
                valid_path = Path(p)
                break

        if not valid_path:
            logger.debug("[ROLLING TRAIN] No se encontró base de datos SQLite con velas vivas.")
            return None

        try:
            with sqlite3.connect(str(valid_path)) as conn:
                # Comprobar si existe tabla de velas (candles / klines)
                cur = conn.cursor()
                cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE '%candle%' OR name LIKE '%kline%')")
                tables = [r[0] for r in cur.fetchall()]
                if not tables:
                    return None

                table_name = tables[0]
                query = f"SELECT timestamp, open, high, low, close, volume FROM {table_name} WHERE symbol LIKE ? ORDER BY timestamp DESC LIMIT ?"
                df = pd.read_sql_query(query, conn, params=(f"%{symbol}%", self.window_candles))
                if df.empty or len(df) < 500:
                    return None
                df = df.sort_values("timestamp").reset_index(drop=True)
                logger.info(f"💾 [ROLLING TRAIN] {len(df)} velas recientes cargadas desde SQLite ({valid_path.name}:{table_name})")
                return df
        except Exception as err:
            logger.debug(f"[ROLLING TRAIN] Consulta SQLite omitida ({err}). Pasando a Data Lake.")
            return None

    def load_fallback_parquet(self) -> Optional[pd.DataFrame]:
        """
        Carga histórica de alta resolución desde el Data Lake Parquet.
        """
        base_dir = Path(__file__).parent.parent.parent
        candidates = [
            base_dir / "engine" / "backtest" / "data" / "btcusdt_15m_1YEAR.parquet",
            base_dir / "engine" / "backtest" / "data" / "BTCUSDT_15m_180d.parquet",
            base_dir / "data" / "btcusdt_15m_1YEAR.parquet"
        ]
        for c in candidates:
            if c.exists():
                try:
                    df = pd.read_parquet(c)
                    logger.info(f"📁 [ROLLING TRAIN] Data Lake cargado: {c.name} ({len(df)} velas)")
                    return df.tail(self.window_candles).copy()
                except Exception as e:
                    logger.error(f"[ROLLING TRAIN] Error leyendo parquet {c}: {e}")
        return None

    def execute_walk_forward_validation(self, X: pd.DataFrame, y: pd.Series) -> Tuple[float, float, xgb.XGBClassifier]:
        """
        Ejecuta validación temporal rodante sin fuga de información (Walk-Forward Time Series Split).
        Retorna: (mean_out_of_sample_accuracy, mean_out_of_sample_precision, best_model)
        """
        n_samples = len(X)
        fold_size = n_samples // (self.n_splits + 1)
        accuracies = []
        precisions = []
        last_model = None

        for fold in range(1, self.n_splits + 1):
            train_end = fold * fold_size
            test_end = min(train_end + fold_size, n_samples)

            X_tr, y_tr = X.iloc[:train_end], y.iloc[:train_end]
            X_te, y_te = X.iloc[train_end:test_end], y.iloc[train_end:test_end]

            if len(X_te) < 50:
                continue

            fold_model = xgb.XGBClassifier(
                n_estimators=120,
                learning_rate=0.04,
                max_depth=5,
                subsample=0.85,
                colsample_bytree=0.80,
                eval_metric="logloss",
                random_state=42 + fold
            )
            fold_model.fit(X_tr, y_tr, eval_set=[(X_te, y_te)], verbose=False)

            preds = fold_model.predict(X_te)
            acc = float(accuracy_score(y_te, preds))
            prec = float(precision_score(y_te, preds, zero_division=0))

            accuracies.append(acc)
            precisions.append(prec)
            last_model = fold_model

        mean_acc = float(np.mean(accuracies)) if accuracies else 0.0
        mean_prec = float(np.mean(precisions)) if precisions else 0.0
        return mean_acc, mean_prec, last_model

    def train_and_atomic_hot_reload(self, force: bool = False) -> Dict[str, Any]:
        """
        Ejecuta el pipeline completo de reentrenamiento Walk-Forward.
        Si la precisión fuera de muestra supera min_accuracy, reemplaza atómicamente
        el modelo en disco y notifica al SlingshotML en memoria para Hot-Reload.
        """
        start_t = time.time()
        # 1. Cargar velas
        df = self.load_recent_candles_from_sqlite()
        if df is None:
            df = self.load_fallback_parquet()

        if df is None or len(df) < 500:
            logger.warning("⚠️ [ROLLING TRAIN] Datos insuficientes para reentrenamiento Walk-Forward.")
            return {"status": "skipped", "reason": "insufficient_data"}

        # 2. Generar Features
        logger.info(f"⚙️ [ROLLING TRAIN] Procesando features estacionarias ({len(df)} velas)...")
        ml_dataset = self.engineer.prepare_dataset(df, classification=True)

        to_drop = ["timestamp", "open", "high", "low", "close", "number_of_trades", "TARGET"]
        feature_cols = [c for c in ml_dataset.columns if c not in to_drop and pd.api.types.is_numeric_dtype(ml_dataset[c])]

        X = ml_dataset[feature_cols]
        y = ml_dataset["TARGET"]

        # 3. Validación Walk-Forward
        mean_acc, mean_prec, candidate_model = self.execute_walk_forward_validation(X, y)
        elapsed = round(time.time() - start_t, 2)
        logger.info(f"🧪 [ROLLING TRAIN] Walk-Forward completado en {elapsed}s | OOS Accuracy: {mean_acc:.2%} | OOS Precision: {mean_prec:.2%}")

        # 4. Decisión de Promoción Fail-Safe
        is_promoted = (mean_acc >= self.min_accuracy) or force
        models_dir = Path(__file__).parent / "models"
        models_dir.mkdir(parents=True, exist_ok=True)
        prod_model_path = models_dir / "slingshot_xgb_15m_v2.json"

        if is_promoted and candidate_model is not None:
            temp_model_path = models_dir / f"candidate_{int(time.time())}.json"
            candidate_model.save_model(str(temp_model_path))

            # Reemplazo atómico
            shutil.move(str(temp_model_path), str(prod_model_path))
            logger.info(f"🏆 [ROLLING TRAIN] Modelo promovido exitosamente con {mean_acc:.2%} de Accuracy.")

            # 5. Hot-Reload en memoria en SlingshotML
            try:
                from engine.ml.inference import ml_engine
                if hasattr(ml_engine, "reload_model"):
                    ml_engine.reload_model()
                else:
                    ml_engine.model.load_model(str(prod_model_path))
                    ml_engine.is_loaded = True
                    logger.info("🔥 [ROLLING TRAIN] Hot-Reload completado en ml_engine (Zero-Downtime).")
            except Exception as reload_err:
                logger.error(f"[ROLLING TRAIN] Error en Hot-Reload: {reload_err}")

            return {
                "status": "promoted",
                "accuracy": mean_acc,
                "precision": mean_prec,
                "elapsed_seconds": elapsed,
                "samples": len(X)
            }
        else:
            logger.warning(f"🛡️ [ROLLING TRAIN] Candidato rechazado ({mean_acc:.2%} < {self.min_accuracy:.2%}). Preservando modelo actual.")
            return {
                "status": "rejected",
                "accuracy": mean_acc,
                "min_required": self.min_accuracy,
                "elapsed_seconds": elapsed
            }


rolling_trainer = RollingWalkForwardTrainer()
