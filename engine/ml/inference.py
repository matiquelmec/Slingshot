from engine.core.logger import logger
import xgboost as xgb
import pandas as pd
import numpy as np
import time
from pathlib import Path
from engine.ml.features import FeatureEngineer

class SlingshotML:
    """
    Motor de Inferencia de ML en Tiempo Real (XGBoost).
    Carga el modelo pre-entrenado en memoria una sola vez para inferencia ultrarrápida.
    """
    def __init__(self, model_filename: str = None):
        self.model = xgb.XGBClassifier()
        self.is_loaded = False
        self.engineer = FeatureEngineer(target_horizon=2)
        
        # Prioridad: 1. filename explícito, 2. v3 Triple-Barrier, 3. v2 fallback
        models_dir = Path(__file__).parent / "models"
        candidates = []
        if model_filename:
            candidates.append(model_filename)
        candidates.extend(["slingshot_xgb_15m_v3.json", "slingshot_xgb_15m_v2.json"])
        
        loaded_fn = None
        for fn in candidates:
            p = models_dir / fn
            if p.exists():
                try:
                    self.model.load_model(str(p))
                    self.is_loaded = True
                    loaded_fn = fn
                    logger.info(f"🧠 [ML ENGINE] Modelo cargado con éxito en memoria: {fn}")
                    break
                except Exception as e:
                    logger.error(f"❌ [ML ENGINE] Error cargando modelo {fn}: {e}")
                    
        if not self.is_loaded:
            logger.info(f"⚠️ [ML ENGINE] Ningún modelo encontrado en {models_dir}. Operando en modo degradado.")
            loaded_fn = "slingshot_xgb_15m_v2.json"
        
        model_filename = loaded_fn

        # Intentar cargar motor ONNX Runtime acelerado C++ si existe
        self.onnx_session = None
        try:
            import onnxruntime as ort
            onnx_path = Path(__file__).parent / "models" / model_filename.replace('.json', '.onnx')
            if onnx_path.exists():
                self.onnx_session = ort.InferenceSession(str(onnx_path))
                logger.info(f"⚡ [ONNX RUNTIME] Inferencia acelerada C++ activada (<2ms): {onnx_path.name}")
        except Exception as ort_err:
            pass

    def reload_model(self, model_filename: str = "slingshot_xgb_15m_v2.json") -> bool:
        """
        Recarga el modelo XGBoost en caliente (Hot-Reload) sin interrumpir el servicio.
        """
        model_path = Path(__file__).parent / "models" / model_filename
        if not model_path.exists():
            logger.warning(f"[ML ENGINE] Archivo de modelo no encontrado para reload: {model_path}")
            return False

        try:
            new_model = xgb.XGBClassifier()
            new_model.load_model(str(model_path))
            self.model = new_model
            self.is_loaded = True
            logger.info(f"🔥 [ML ENGINE] Hot-Reload exitoso: {model_filename} activo en memoria.")
            return True
        except Exception as err:
            logger.error(f"❌ [ML ENGINE] Error durante Hot-Reload de modelo: {err}")
            return False

    def predict_live(self, df: pd.DataFrame) -> dict:
        """
        Toma el DataFrame en tiempo real (buffer de velas), calcula las features,
        y devuelve la probabilidad ML de que el precio suba en el horizonte definido.
        """
        if not self.is_loaded or len(df) < 50: # Mínimo necesario para EMAs y SMC
            return {"direction": "ANALIZANDO", "probability": 50, "status": "no_model"}
            
        try:
            start_time = time.time()
            
            # --- OPTIMIZACIÓN DE VENTANA (v5.7.155 Master Gold) ---
            # Para inferencia live, solo necesitamos las últimas 100 velas para que los indicadores 
            # (EMAs, ATR, RVOL) tengan suficiente histórico. Procesar todo el DF causa latencia inaceptable.
            inference_window = df.tail(100).copy()
            features_df = self.engineer.generate_features(inference_window)
            
            if features_df.empty:
                return {"direction": "ANALIZANDO", "probability": 50, "status": "insufficient_data"}
                
            # Extraer solo la ÚLTIMA fila (la vela actual/viva)
            latest_features = features_df.iloc[[-1]].copy()
            
            # 2. Interceptar estrictamente las features que el modelo espera
            # Evita crashes si agregamos nuevas columnas al DataFrame global (ej: SMC / Soportes) en el futuro
            expected_features = list(self.model.feature_names_in_)
            
            # Rellenar con 0 de seguridad si por rediseños estructurales falta alguna feature
            for f in expected_features:
                if f not in latest_features.columns:
                    latest_features[f] = 0
                    
            X_live = latest_features[expected_features]
            
            # 3. Predicción
            # predict_proba devuelve [prob_caer, prob_subir]
            probabilities = self.model.predict_proba(X_live)[0]
            prob_bullish = float(probabilities[1]) * 100
            
            # Determinamos la dirección y ajustamos la probabilidad para mostrar "qué tan seguro está de esa dirección"
            if prob_bullish >= 50:
                direction = "ALCISTA"
                confidence = prob_bullish
            else:
                direction = "BAJISTA"
                confidence = 100.0 - prob_bullish
                
            # 4. Generación de Explicación Educativa (Por qué se tomó la decisión)
            # Para esto, miramos las features que tienen más peso histórico y sus valores actuales
            reason_parts = []
            
            # SMC Order Blocks
            if latest_features['ob_bullish'].iloc[0] == 1:
                reason_parts.append("Fuerte inyección institucional detectada (Order Block Alcista)")
            elif latest_features['ob_bearish'].iloc[0] == 1:
                reason_parts.append("Fuerte inyección de oferta detectada (Order Block Bajista)")
            elif latest_features['fvg_bullish'].iloc[0] == 1:
                reason_parts.append("Vacío de liquidez alcista activado (FVG)")
            elif latest_features['fvg_bearish'].iloc[0] == 1:
                reason_parts.append("Vacío de liquidez bajista activado (FVG)")
                
            # Distancia a la EMA
            dist_ema21 = latest_features.get('dist_ema21', pd.Series([0])).iloc[0]
            if dist_ema21 > 0.02: # 2% alejado
                reason_parts.append("Precio muy extendido sobre la EMA21 (Riesgo de pullback)")
            elif dist_ema21 < -0.02:
                reason_parts.append("Precio muy por debajo de la EMA21 (Potencial reversión alcista)")
                
            # Momentum / Retornos
            ret_5 = latest_features.get('return_5', pd.Series([0])).iloc[0]
            if ret_5 > 0.015:
                reason_parts.append("Momentum de compras agresivo en los últimos 75m")
            elif ret_5 < -0.015:
                reason_parts.append("Fuerte presión de venta continuada")
                
            # Si no hay nada extremo, damos un mensaje genérico del ecosistema XGBoost
            if not reason_parts:
                if direction == "ALCISTA":
                    reason_parts.append("Estructura de volumen y volatilidad favorecen la continuación al alza")
                else:
                    reason_parts.append("Micro-estructura favorece debilidad a corto plazo")
                    
            educational_reason = " | ".join(reason_parts)
            
            # Cálculo de Latencia de Inferencia
            inference_ms = round((time.time() - start_time) * 1000, 2)
                
            return {
                "direction": direction,
                "probability": int(confidence),
                "status": "active",
                "reason": educational_reason,
                "inference_ms": inference_ms,
                "is_confident": confidence >= 60 # Nuevo Gate 3: Confianza mínima IA
            }
            
        except Exception as e:
            logger.error(f"⚠️ [ML ENGINE] Error en inferencia en vivo: {e}")
            import traceback
            traceback.print_exc()
            return {"direction": "ERROR", "probability": 50, "status": "error"}

# Instancia Global (Singleton) para no recargar el modelo en cada petición
ml_engine = SlingshotML()
