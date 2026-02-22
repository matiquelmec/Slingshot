import xgboost as xgb
import pandas as pd
import numpy as np
from pathlib import Path
from engine.ml.features import FeatureEngineer

class SlingshotML:
    """
    Motor de Inferencia de ML en Tiempo Real (XGBoost).
    Carga el modelo pre-entrenado en memoria una sola vez para inferencia ultrarrápida.
    """
    def __init__(self, model_filename: str = "slingshot_xgb_15m_v2.json"):
        self.model = xgb.XGBClassifier()
        self.is_loaded = False
        self.engineer = FeatureEngineer(target_horizon=2)
        
        # Intentar cargar el modelo al instanciar
        model_path = Path(__file__).parent / "models" / model_filename
        if model_path.exists():
            try:
                self.model.load_model(str(model_path))
                self.is_loaded = True
                print(f"🧠 [ML ENGINE] Modelo cargado con éxito en memoria: {model_filename}")
            except Exception as e:
                print(f"❌ [ML ENGINE] Error cargando el modelo: {e}")
        else:
            print(f"⚠️ [ML ENGINE] Modelo no encontrado en {model_path}. Operando en modo degrado.")

    def predict_live(self, df: pd.DataFrame) -> dict:
        """
        Toma el DataFrame en tiempo real (buffer de velas), calcula las features,
        y devuelve la probabilidad ML de que el precio suba en el horizonte definido.
        """
        if not self.is_loaded or len(df) < 50: # Mínimo necesario para EMAs y SMC
            return {"direction": "ANALIZANDO", "probability": 50, "status": "no_model"}
            
        try:
            # 1. Generar features para la vela actual (la última del DataFrame)
            # Pasamos todo el DF a la feature factory porque los indicadores necesitan el histórico (rollings)
            features_df = self.engineer.generate_features(df)
            
            if features_df.empty:
                return {"direction": "ANALIZANDO", "probability": 50, "status": "insufficient_data"}
                
            # Extraer solo la ÚLTIMA fila (la vela actual/viva)
            latest_features = features_df.iloc[[-1]].copy()
            
            # 2. Limpiar las columnas (Excluir 'timestamp', 'open', 'high', 'low', 'close', etc)
            to_drop = ['timestamp', 'open', 'high', 'low', 'close', 'number_of_trades', 'TARGET', 'close_time', 'quote_asset_volume', 'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore']
            feature_cols = [col for col in latest_features.columns if col not in to_drop and pd.api.types.is_numeric_dtype(latest_features[col])]
            
            X_live = latest_features[feature_cols]
            
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
                
            return {
                "direction": direction,
                "probability": int(confidence),
                "status": "active",
                "reason": educational_reason
            }
            
        except Exception as e:
            print(f"⚠️ [ML ENGINE] Error en inferencia en vivo: {e}")
            import traceback
            traceback.print_exc()
            return {"direction": "ERROR", "probability": 50, "status": "error"}

# Instancia Global (Singleton) para no recargar el modelo en cada petición
ml_engine = SlingshotML()
