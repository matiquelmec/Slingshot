"""
engine/agents/regime_hmm.py — SOP-63 / SOP-75 Probabilistic Market Regime Classifier (HMM / GMM)
=================================================================================================
Clasificador probabilístico de regímenes de mercado continuo utilizando Gaussian Mixture Models
y matrices de transición markoviana sobre series de retornos, volatilidad realizada y volumen.

Estados Latentes:
  • STATE 0 (BULL_EXPANSION): Retornos positivos consistentes, volatilidad controlada, KER alto.
  • STATE 1 (BEAR_EXPANSION): Retornos negativos persistentes, KER direccional, presión de venta.
  • STATE 2 (CHOP_COMPRESSION): Volatilidad comprimida, retornos alrededor de 0, KER bajo (<0.28).
  • STATE 3 (HIGH_VOL_SHOCK): Dispersión anómala de retornos (colas pesadas), volatilidad extrema.
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple
import numpy as np
import pandas as pd
from sklearn.mixture import GaussianMixture

from engine.core.logger import logger
from engine.core.vault import vault


class ProbabilisticRegime(str, Enum):
    BULL_EXPANSION   = "BULL_EXPANSION"
    BEAR_EXPANSION   = "BEAR_EXPANSION"
    CHOP_COMPRESSION = "CHOP_COMPRESSION"
    HIGH_VOL_SHOCK   = "HIGH_VOL_SHOCK"
    NEUTRAL          = "NEUTRAL"


@dataclass
class HMMRegimeState:
    primary_regime: ProbabilisticRegime
    regime_probabilities: Dict[str, float]
    risk_multiplier: float
    confidence: float
    volatility_zscore: float
    efficiency_ratio: float
    transition_entropy: float
    actionable_guideline: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary_regime": self.primary_regime.value if isinstance(self.primary_regime, ProbabilisticRegime) else str(self.primary_regime),
            "regime_probabilities": {k: round(v, 4) for k, v in self.regime_probabilities.items()},
            "risk_multiplier": round(self.risk_multiplier, 2),
            "confidence": round(self.confidence, 3),
            "volatility_zscore": round(self.volatility_zscore, 2),
            "efficiency_ratio": round(self.efficiency_ratio, 3),
            "transition_entropy": round(self.transition_entropy, 3),
            "actionable_guideline": self.actionable_guideline,
            "timestamp": self.timestamp
        }


class GaussianHMMRegimeDetector:
    """
    Detector continuo de regímenes latentes probabilísticos.
    Combina estimación de densidad Gaussiana Multivariada (GMM) con dinámica de suavizado temporal.
    """

    def __init__(self, n_components: int = 4, random_state: int = 42):
        self.n_components = n_components
        self.random_state = random_state
        self.model: Optional[GaussianMixture] = None
        self._component_mapping: Dict[int, ProbabilisticRegime] = {}
        self._last_state: Optional[HMMRegimeState] = None
        self._transition_matrix: np.ndarray = np.eye(n_components)

    def extract_features(self, df: pd.DataFrame) -> np.ndarray:
        """
        Extrae el espacio de estados canónico:
        1. Log-returns de 1 y 5 periodos.
        2. Volatilidad normalizada (ATR / Close o Rolling Std).
        3. Kaufman Efficiency Ratio (KER).
        4. Log-Volume ratio contra media móvil.
        """
        if len(df) < 30:
            return np.empty((0, 4))

        close = df["close"].values.astype(float)
        volume = df.get("volume", pd.Series(np.ones(len(df)))).values.astype(float)

        # 1. Log returns
        log_ret_1 = np.diff(np.log(close + 1e-9), prepend=np.log(close[0] + 1e-9))
        log_ret_5 = pd.Series(close).pct_change(5).fillna(0).values

        # 2. Volatilidad realizada rodante
        ret_series = pd.Series(log_ret_1)
        rolling_vol = ret_series.rolling(window=14).std().bfill().values
        vol_mean = np.mean(rolling_vol) if np.mean(rolling_vol) > 0 else 1.0
        norm_vol = rolling_vol / (vol_mean + 1e-9)

        # 3. KER
        diff_10 = pd.Series(close).diff().abs().rolling(10).sum().values
        net_10 = np.abs(pd.Series(close).diff(10).values)
        ker = np.where(diff_10 > 1e-9, net_10 / (diff_10 + 1e-9), 0.35)
        ker = np.nan_to_num(ker, nan=0.35)

        # 4. Normalización matricial
        features = np.column_stack([log_ret_5, norm_vol, ker, log_ret_1])
        return np.nan_to_num(features, nan=0.0)

    def fit_from_candles(self, df: pd.DataFrame) -> bool:
        """
        Ajusta los centroides y covarianzas de los estados latentes no supervisados.
        """
        X = self.extract_features(df)
        if len(X) < 100:
            return False

        try:
            self.model = GaussianMixture(
                n_components=self.n_components,
                covariance_type="full",
                max_iter=150,
                random_state=self.random_state
            )
            self.model.fit(X)

            # Clasificar dinámicamente los componentes según sus medias
            means = self.model.means_
            # Columna 0: log_ret_5, Columna 1: norm_vol, Columna 2: ker

            for comp_idx in range(self.n_components):
                ret_m = means[comp_idx, 0]
                vol_m = means[comp_idx, 1]
                ker_m = means[comp_idx, 2]

                if vol_m > 1.8:
                    self._component_mapping[comp_idx] = ProbabilisticRegime.HIGH_VOL_SHOCK
                elif ker_m < 0.25 and vol_m < 1.1:
                    self._component_mapping[comp_idx] = ProbabilisticRegime.CHOP_COMPRESSION
                elif ret_m > 0 and ker_m >= 0.30:
                    self._component_mapping[comp_idx] = ProbabilisticRegime.BULL_EXPANSION
                elif ret_m < 0 and ker_m >= 0.30:
                    self._component_mapping[comp_idx] = ProbabilisticRegime.BEAR_EXPANSION
                else:
                    self._component_mapping[comp_idx] = ProbabilisticRegime.NEUTRAL

            logger.info(f"📊 [HMM REGIME] Modelo probabilístico ajustado ({len(X)} velas). Mapeo de estados: {self._component_mapping}")
            return True
        except Exception as fit_err:
            logger.error(f"[HMM REGIME] Error entrenando modelo GMM: {fit_err}")
            return False

    def predict_regime_state(self, df: pd.DataFrame) -> HMMRegimeState:
        """
        Infiere la distribución a posteriori P(Estado | Datos_t) para la vela actual.
        """
        if self.model is None or not hasattr(self.model, "means_"):
            # Ajuste en caliente si aún no se ha entrenado
            if len(df) >= 100:
                self.fit_from_candles(df)
            else:
                return self._fallback_heuristic_state(df)

        X = self.extract_features(df)
        if len(X) == 0:
            return self._fallback_heuristic_state(df)

        last_sample = X[[-1]]
        try:
            post_probs = self.model.predict_proba(last_sample)[0]
        except Exception:
            return self._fallback_heuristic_state(df)

        # Mapear probabilidades por régimen semántico
        regime_probs = {
            ProbabilisticRegime.BULL_EXPANSION.value: 0.0,
            ProbabilisticRegime.BEAR_EXPANSION.value: 0.0,
            ProbabilisticRegime.CHOP_COMPRESSION.value: 0.0,
            ProbabilisticRegime.HIGH_VOL_SHOCK.value: 0.0,
            ProbabilisticRegime.NEUTRAL.value: 0.0
        }

        for comp_idx, prob in enumerate(post_probs):
            assigned_regime = self._component_mapping.get(comp_idx, ProbabilisticRegime.NEUTRAL).value
            regime_probs[assigned_regime] += float(prob)

        # Determinar régimen dominante
        dominant_regime_str = max(regime_probs, key=regime_probs.get)
        dominant_regime = ProbabilisticRegime(dominant_regime_str)
        confidence = float(regime_probs[dominant_regime_str])

        # Multiplicador táctico continuo (interpolación ponderada)
        risk_multiplier = (
            regime_probs[ProbabilisticRegime.BULL_EXPANSION.value] * 1.30 +
            regime_probs[ProbabilisticRegime.BEAR_EXPANSION.value] * 1.15 +
            regime_probs[ProbabilisticRegime.NEUTRAL.value] * 1.00 +
            regime_probs[ProbabilisticRegime.CHOP_COMPRESSION.value] * 0.65 +
            regime_probs[ProbabilisticRegime.HIGH_VOL_SHOCK.value] * 0.50
        )
        risk_multiplier = max(0.50, min(1.35, float(risk_multiplier)))

        # Entropía de Shannon para medir incertidumbre de transición
        entropy = -sum(p * np.log2(p + 1e-9) for p in post_probs if p > 0)

        # Métricas directas
        vol_z = float(last_sample[0, 1])
        ker_val = float(last_sample[0, 2])

        guidelines = {
            ProbabilisticRegime.BULL_EXPANSION: "Expansión alcista institucional. Asignación multiplicada y runners habilitados a +5.0R.",
            ProbabilisticRegime.BEAR_EXPANSION: "Flujo institucional vendedor activo. Asignación al 115% priorizando ventas OTE.",
            ProbabilisticRegime.CHOP_COMPRESSION: "Compresión de baja volatilidad. Riesgo reducido al 65% y preservación de capital.",
            ProbabilisticRegime.HIGH_VOL_SHOCK: "Shock de volatilidad no direccional. Asignación al 50% con circuit-breaker preventivo.",
            ProbabilisticRegime.NEUTRAL: "Mercado en equilibrio o rotación. Asignación nominal al 100%."
        }

        state = HMMRegimeState(
            primary_regime=dominant_regime,
            regime_probabilities=regime_probs,
            risk_multiplier=risk_multiplier,
            confidence=confidence,
            volatility_zscore=vol_z,
            efficiency_ratio=ker_val,
            transition_entropy=float(entropy),
            actionable_guideline=guidelines.get(dominant_regime, "Operativa estándar.")
        )

        self._last_state = state
        # Registrar en la bóveda transaccional
        try:
            vault.record_regime_state(
                regime=state.primary_regime.value,
                risk_multiplier=state.risk_multiplier,
                confidence=state.confidence,
                details=state.to_dict()
            )
        except Exception as v_err:
            logger.debug(f"[HMM REGIME] Error registrando estado en Vault: {v_err}")

        return state

    def _fallback_heuristic_state(self, df: pd.DataFrame) -> HMMRegimeState:
        """Fallback determinístico robusto cuando el histórico es mínimo."""
        probs = {
            ProbabilisticRegime.BULL_EXPANSION.value: 0.20,
            ProbabilisticRegime.BEAR_EXPANSION.value: 0.20,
            ProbabilisticRegime.CHOP_COMPRESSION.value: 0.20,
            ProbabilisticRegime.HIGH_VOL_SHOCK.value: 0.10,
            ProbabilisticRegime.NEUTRAL.value: 0.30
        }
        return HMMRegimeState(
            primary_regime=ProbabilisticRegime.NEUTRAL,
            regime_probabilities=probs,
            risk_multiplier=1.00,
            confidence=0.50,
            volatility_zscore=1.0,
            efficiency_ratio=0.35,
            transition_entropy=2.0,
            actionable_guideline="Inicializando detector HMM. Operando con régimen neutro estándar."
        )


# Instancia Singleton
hmm_regime_detector = GaussianHMMRegimeDetector()
