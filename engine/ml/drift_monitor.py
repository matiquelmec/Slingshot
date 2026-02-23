"""
Nivel 5: Drift Monitor — Auto-Supervisión del Modelo ML.
=========================================================
Detecta cuándo el modelo XGBoost empieza a perder relevancia porque el
mercado cambió de régimen y los datos de entrenamiento ya no representan
la distribución actual de los features.

Usa dos métricas complementarias:
  • PSI (Population Stability Index): detecta shift en la distribución de features
    entre el set de referencia (entrenamiento) y los datos vivos recientes.
    PSI < 0.10 → estable
    PSI 0.10–0.25 → cambio moderado (⚠️ revisión recomendada)
    PSI > 0.25 → drift severo (🚨 reentrenar)

  • Accuracy rolling: compara las predicciones del modelo con el resultado
    real del mercado en las últimas N velas cerradas.

El monitor emite alertas al WebSocket y opcionalmente al Bot de Telegram.
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional
import time

# ── Umbrales PSI ─────────────────────────────────────────────────────────────
PSI_STABLE   = 0.10   # Verde: sin cambios significativos
PSI_MODERATE = 0.25   # Amarillo: hay drift, modelo degradado
# PSI > 0.25 → Rojo: modelo obsoleto, reentrenar urgente

# Features más críticas para monitorizar (subset clave del modelo)
KEY_FEATURES = [
    'rsi', 'macd', 'macd_signal', 'bb_width',
    'sma_fast', 'sma_slow', 'volume', 'atr'
]


@dataclass
class DriftReport:
    """Resultado del análisis de drift del modelo."""
    timestamp: float                    = field(default_factory=time.time)

    # PSI por feature
    psi_scores: dict[str, float]        = field(default_factory=dict)
    psi_max: float                      = 0.0
    psi_mean: float                     = 0.0
    features_in_drift: list[str]        = field(default_factory=list)

    # Accuracy rolling
    rolling_accuracy: float             = 0.0
    predictions_evaluated: int          = 0

    # Estado global
    drift_level: str                    = 'STABLE'  # STABLE / MODERATE / SEVERE
    alert_triggered: bool               = False
    recommendation: str                 = "Modelo estable. Sin acción requerida."

    def to_dict(self) -> dict:
        return {
            "timestamp":             self.timestamp,
            "psi_max":               round(self.psi_max, 4),
            "psi_mean":              round(self.psi_mean, 4),
            "features_in_drift":     self.features_in_drift,
            "rolling_accuracy":      round(self.rolling_accuracy, 4),
            "predictions_evaluated": self.predictions_evaluated,
            "drift_level":           self.drift_level,
            "alert_triggered":       self.alert_triggered,
            "recommendation":        self.recommendation,
        }


class DriftMonitor:
    """
    Monitor de obsolescencia del modelo ML.

    Uso:
        monitor = DriftMonitor()
        monitor.set_reference(df_training_features)  # Una sola vez al iniciar

        # En cada cierre de vela:
        report = monitor.check(df_live_features, predictions, actuals)
        if report.alert_triggered:
            await telegram.send_drift_alert_async(report.to_dict())
    """

    def __init__(self, window_size: int = 500, accuracy_window: int = 100):
        """
        :param window_size: Número de velas recientes para comparar distribuciones (PSI)
        :param accuracy_window: Número de predicciones para calcular accuracy rolling
        """
        self.window_size      = window_size
        self.accuracy_window  = accuracy_window

        # Distribución de referencia (del set de entrenamiento)
        self._reference_df: Optional[pd.DataFrame] = None
        self._reference_bins: dict[str, np.ndarray] = {}

        # Historial de predicciones y resultados reales (circular buffer)
        self._pred_history: list[int] = []
        self._actual_history: list[int] = []

        # Cache del último reporte
        self._last_report: Optional[DriftReport] = None
        self._last_check_time: float = 0.0
        self._check_interval: float  = 60.0 * 15  # Evaluar cada 15 min max

    def set_reference(self, df_reference: pd.DataFrame) -> None:
        """
        Define la distribución de referencia del entrenamiento.
        Llamar una sola vez al arrancar el sistema.
        """
        available = [f for f in KEY_FEATURES if f in df_reference.columns]
        self._reference_df = df_reference[available].dropna().tail(self.window_size)

        # Pre-calcular bins por feature (10 buckets iguales)
        self._reference_bins = {}
        for feat in available:
            vals = self._reference_df[feat].values
            # Usar percentiles para bins robustos (evita outliers que distorsionan el PSI)
            bins = np.nanpercentile(vals, np.linspace(0, 100, 11))
            bins = np.unique(bins)  # Eliminar duplicados
            if len(bins) < 3:
                bins = np.array([vals.min() - 1e-9, vals.mean(), vals.max() + 1e-9])
            self._reference_bins[feat] = bins

        print(f"[DRIFT] ✅ Referencia establecida con {len(self._reference_df)} filas y {len(available)} features.")

    def record_prediction(self, predicted: int, actual: int) -> None:
        """
        Registra una predicción y el resultado real para calcular accuracy rolling.
        :param predicted: 1 = subida, 0 = bajada (predicción del modelo)
        :param actual: 1 = subida, 0 = bajada (lo que realmente pasó)
        """
        self._pred_history.append(predicted)
        self._actual_history.append(actual)
        # Mantener solo la ventana más reciente
        if len(self._pred_history) > self.accuracy_window:
            self._pred_history.pop(0)
            self._actual_history.pop(0)

    @staticmethod
    def _compute_psi_for_feature(
        reference_vals: np.ndarray,
        live_vals: np.ndarray,
        bins: np.ndarray,
        epsilon: float = 1e-6
    ) -> float:
        """
        Calcula el PSI entre la distribución de referencia y la distribución en vivo.

        Formula: PSI = Σ (P_live - P_ref) * ln(P_live / P_ref)
        """
        # Frecuencias por bin
        ref_counts  = np.histogram(reference_vals, bins=bins)[0]
        live_counts = np.histogram(live_vals, bins=bins)[0]

        # Convertir a proporciones (con epsilon para evitar log(0))
        ref_pct  = (ref_counts  + epsilon) / (len(reference_vals)  + epsilon * len(bins))
        live_pct = (live_counts + epsilon) / (len(live_vals) + epsilon * len(bins))

        psi = np.sum((live_pct - ref_pct) * np.log(live_pct / ref_pct))
        return float(psi)

    def check(self, df_live: pd.DataFrame) -> Optional[DriftReport]:
        """
        Ejecuta la comprobación de drift. Retorna None si el caché está fresco.

        :param df_live: DataFrame reciente de los últimos N cierres de vela
        :return: DriftReport con el estado actual del modelo
        """
        now = time.time()
        if now - self._last_check_time < self._check_interval:
            return self._last_report  # Retornar caché

        if self._reference_df is None or len(self._reference_bins) == 0:
            print("[DRIFT] ⚠️  Sin distribución de referencia. Llamar set_reference() primero.")
            return None

        self._last_check_time = now
        report = DriftReport()

        # ── 1. Calcular PSI por feature ───────────────────────────────────
        live_window = df_live.tail(self.window_size)
        for feat, bins in self._reference_bins.items():
            if feat not in live_window.columns:
                continue
            live_vals = live_window[feat].dropna().values
            ref_vals  = self._reference_df[feat].dropna().values

            if len(live_vals) < 30:
                continue  # Muestra insuficiente

            psi = self._compute_psi_for_feature(ref_vals, live_vals, bins)
            report.psi_scores[feat] = round(psi, 4)

            if psi > PSI_MODERATE:
                report.features_in_drift.append(feat)

        if report.psi_scores:
            report.psi_max  = max(report.psi_scores.values())
            report.psi_mean = sum(report.psi_scores.values()) / len(report.psi_scores)

        # ── 2. Accuracy rolling ───────────────────────────────────────────
        if len(self._pred_history) >= 10:
            correct = sum(p == a for p, a in zip(self._pred_history, self._actual_history))
            report.rolling_accuracy     = correct / len(self._pred_history)
            report.predictions_evaluated = len(self._pred_history)

        # ── 3. Clasificar nivel de drift ──────────────────────────────────
        n_severe_features = len(report.features_in_drift)

        if report.psi_max > PSI_MODERATE or n_severe_features >= 3:
            report.drift_level     = 'SEVERE'
            report.alert_triggered = True
            report.recommendation  = (
                f"🚨 Drift severo en {n_severe_features} features ({', '.join(report.features_in_drift[:3])}). "
                f"PSI máximo: {report.psi_max:.3f}. "
                f"Accuracy rolling: {report.rolling_accuracy*100:.1f}%. "
                "Reentrenar el modelo con datos recientes es urgente."
            )
        elif report.psi_max > PSI_STABLE or (
            report.predictions_evaluated >= 50 and report.rolling_accuracy < 0.52
        ):
            report.drift_level     = 'MODERATE'
            report.alert_triggered = True
            report.recommendation  = (
                f"⚠️ Drift moderado detectado. PSI max: {report.psi_max:.3f}. "
                f"Accuracy rolling: {report.rolling_accuracy*100:.1f}%. "
                "Revisar el modelo en los próximos días."
            )
        else:
            report.drift_level     = 'STABLE'
            report.alert_triggered = False
            report.recommendation  = (
                f"✅ Modelo estable. PSI max: {report.psi_max:.3f}. "
                f"Accuracy rolling: {report.rolling_accuracy*100:.1f}%."
            )

        self._last_report = report

        print(
            f"[DRIFT] Nivel={report.drift_level} | "
            f"PSI max={report.psi_max:.3f} | "
            f"Accuracy={report.rolling_accuracy*100:.1f}% ({report.predictions_evaluated} preds)"
        )
        if report.alert_triggered:
            print(f"[DRIFT] 🚨 ALERTA: {report.recommendation}")

        return report

    def reset(self) -> None:
        """Limpia el historial de predicciones y el caché."""
        self._pred_history.clear()
        self._actual_history.clear()
        self._last_report = None
        self._last_check_time = 0.0
        print("[DRIFT] Estado reseteado.")


# ── Singleton global ──────────────────────────────────────────────────────────
drift_monitor = DriftMonitor(window_size=500, accuracy_window=100)


# ── Test rápido ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import numpy as np
    import pandas as pd

    print("🔬 Test Drift Monitor\n")

    # Crear datos de referencia simulados
    np.random.seed(42)
    n = 600
    df_ref = pd.DataFrame({
        'rsi':        np.random.normal(50, 15, n).clip(0, 100),
        'macd':       np.random.normal(0, 100, n),
        'macd_signal':np.random.normal(0, 80, n),
        'bb_width':    np.random.normal(0.03, 0.01, n).clip(0.005),
        'sma_fast':   np.random.normal(90000, 5000, n),
        'sma_slow':   np.random.normal(88000, 4000, n),
        'volume':     np.abs(np.random.normal(1e9, 3e8, n)),
        'atr':        np.abs(np.random.normal(1500, 400, n)),
    })

    monitor = DriftMonitor()
    monitor.set_reference(df_ref)

    # Caso 1: Datos similares al entrenamiento (sin drift)
    df_live_ok = pd.DataFrame({
        'rsi':        np.random.normal(50, 15, 500).clip(0, 100),
        'macd':       np.random.normal(0, 100, 500),
        'macd_signal':np.random.normal(0, 80, 500),
        'bb_width':   np.random.normal(0.03, 0.01, 500).clip(0.005),
        'sma_fast':   np.random.normal(90000, 5000, 500),
        'sma_slow':   np.random.normal(88000, 4000, 500),
        'volume':     np.abs(np.random.normal(1e9, 3e8, 500)),
        'atr':        np.abs(np.random.normal(1500, 400, 500)),
    })
    for i in range(100):
        monitor.record_prediction(np.random.randint(0, 2), np.random.randint(0, 2))

    report = monitor.check(df_live_ok)
    print(f"\n📊 Caso SIN drift: nivel={report.drift_level}, PSI_max={report.psi_max:.3f}")

    # Caso 2: Mercado muy diferente (bear market extremo → drift severo)
    monitor._last_check_time = 0  # Forzar recálculo
    df_live_drift = pd.DataFrame({
        'rsi':        np.random.normal(20, 5, 500).clip(0, 100),   # RSI muy bajo
        'macd':       np.random.normal(-500, 200, 500),               # MACD negativo extremo
        'macd_signal':np.random.normal(-400, 150, 500),
        'bb_width':   np.random.normal(0.08, 0.02, 500).clip(0.01),  # Volatilidad 3x mayor
        'sma_fast':   np.random.normal(70000, 3000, 500),             # Precio mucho más bajo
        'sma_slow':   np.random.normal(80000, 4000, 500),
        'volume':     np.abs(np.random.normal(5e9, 2e9, 500)),        # Volumen 5x mayor
        'atr':        np.abs(np.random.normal(5000, 1000, 500)),      # ATR 3x mayor
    })
    report2 = monitor.check(df_live_drift)
    print(f"\n📊 Caso CON drift severo: nivel={report2.drift_level}, PSI_max={report2.psi_max:.3f}")
    print(f"   Features en drift: {report2.features_in_drift}")
    print(f"   Recomendación: {report2.recommendation}")
