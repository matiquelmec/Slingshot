"""
engine/agents/regime_agent.py — SOP-63 Quantitative Market Regime & Dynamic Allocation Agent
=============================================================================================
Agente autónomo de inferencia de régimen macro y asignación adaptativa de riesgo.
Monitorea continuamente:
1. Volatilidad realizada y fuerza direccional (ADX & KER multiactivo).
2. Alineación macro de la Trinidad (BTC, SOL, FET).
3. Distancia al VWAP institucional y dispersión de momentum.
4. Salud del modelo de Meta-Labeling ML (Drift Monitor PSI).

Determina el estado del mercado:
• BULL_EXPANSION   (1.25x a 1.35x riesgo | Runner elástico a +5.0R habilitado)
• BEAR_EXPANSION   (1.10x a 1.20x riesgo | Short momentum OTE)
• CHOP_COMPRESSION (0.60x a 0.75x riesgo | Preservación de capital, TP1 prioritario)
• HIGH_VOL_SHOCK   (0.50x riesgo o circuit-breaker preventivo)
• NEUTRAL          (1.00x riesgo plano estándar)
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import pandas as pd
import numpy as np

from engine.core.logger import logger
from engine.core.vault import vault
from engine.ml.drift_monitor import DriftReport
from engine.ml.train import safe_auto_retrain


class MarketRegime(str, Enum):
    BULL_EXPANSION   = "BULL_EXPANSION"
    BEAR_EXPANSION   = "BEAR_EXPANSION"
    CHOP_COMPRESSION = "CHOP_COMPRESSION"
    HIGH_VOL_SHOCK   = "HIGH_VOL_SHOCK"
    NEUTRAL          = "NEUTRAL"


@dataclass
class RegimeAssessment:
    regime: MarketRegime
    confidence: float
    risk_multiplier: float
    adx_avg: float
    ker_avg: float
    btc_htf_trend: str
    actionable_guideline: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "regime": self.regime.value if isinstance(self.regime, MarketRegime) else str(self.regime),
            "confidence": round(self.confidence, 3),
            "risk_multiplier": round(self.risk_multiplier, 2),
            "adx_avg": round(self.adx_avg, 2),
            "ker_avg": round(self.ker_avg, 3),
            "btc_htf_trend": self.btc_htf_trend,
            "actionable_guideline": self.actionable_guideline,
            "timestamp": self.timestamp
        }


class SlingshotRegimeAgent:
    """
    Agente Autónomo de Régimen Cuantitativo y Supervisión Táctica.
    """

    def __init__(self):
        self.last_assessment: Optional[RegimeAssessment] = None

    def evaluate_market_regime(
        self,
        symbols_data: Dict[str, pd.DataFrame],
        btc_htf_trend: str = "NEUTRAL"
    ) -> RegimeAssessment:
        """
        Evalúa el régimen multiactivo a partir de los DataFrames recientes de los líderes del mercado.
        """
        if not symbols_data:
            return RegimeAssessment(
                regime=MarketRegime.NEUTRAL,
                confidence=0.50,
                risk_multiplier=1.00,
                adx_avg=20.0,
                ker_avg=0.35,
                btc_htf_trend=btc_htf_trend,
                actionable_guideline="Sin datos suficientes de mercado. Operando en régimen neutro estándar."
            )

        adx_list = []
        ker_list = []
        close_changes = []

        for sym, df in symbols_data.items():
            if df is None or df.empty or len(df) < 20:
                continue

            # ADX
            if "adx" in df.columns:
                adx_list.append(float(df["adx"].dropna().iloc[-1]))
            else:
                adx_list.append(22.0)

            # KER (Kaufman Efficiency Ratio)
            if "ker" in df.columns:
                ker_list.append(float(df["ker"].dropna().iloc[-1]))
            elif "close" in df.columns and len(df) >= 11:
                chg = abs(df["close"].iloc[-1] - df["close"].iloc[-11])
                path = df["close"].diff().abs().iloc[-10:].sum()
                ker_list.append(chg / (path + 1e-9))
            else:
                ker_list.append(0.35)

            # Volatilidad / Cambio de precio
            if "close" in df.columns and len(df) >= 20:
                pct_chg = (df["close"].iloc[-1] - df["close"].iloc[-20]) / df["close"].iloc[-20] * 100.0
                close_changes.append(pct_chg)

        adx_mean = float(np.mean(adx_list)) if adx_list else 22.0
        ker_mean = float(np.mean(ker_list)) if ker_list else 0.35
        momentum_mean = float(np.mean(close_changes)) if close_changes else 0.0

        # ── REGLAS CUANTITATIVAS INSTITUCIONALES DE CLASIFICACIÓN ──

        # 1. Shock de Volatilidad Extrema (ADX > 45 con dispersión caótica)
        if adx_mean >= 45.0 and ker_mean < 0.30:
            regime = MarketRegime.HIGH_VOL_SHOCK
            multiplier = 0.50
            confidence = 0.85
            guideline = "Shock de alta volatilidad no direccional. Asignación reducida al 50% y defensiva activa."

        # 2. Compresión y Mercado Muerto (ADX < 18 y KER < 0.28)
        elif adx_mean < 18.5 and ker_mean < 0.28:
            regime = MarketRegime.CHOP_COMPRESSION
            multiplier = 0.65
            confidence = 0.90
            guideline = "Mercado lateral comprimido (Chop). Reducir tamaño al 65% para evitar comisiones innecesarias."

        # 3. Expansión Alcista Fuerte (BTC Bullish, KER alto y momentum positivo)
        elif (btc_htf_trend.upper() == "BULLISH" or momentum_mean > 1.5) and ker_mean >= 0.40 and adx_mean >= 20.0:
            regime = MarketRegime.BULL_EXPANSION
            multiplier = 1.30
            confidence = 0.88
            guideline = "Expansión alcista institucional. Asignación al 130% y búsqueda de Runners elásticos a +5.0R."

        # 4. Expansión Bajista Estructurada (BTC Bearish, KER alto y momentum negativo)
        elif (btc_htf_trend.upper() == "BEARISH" or momentum_mean < -1.5) and ker_mean >= 0.40 and adx_mean >= 20.0:
            regime = MarketRegime.BEAR_EXPANSION
            multiplier = 1.15
            confidence = 0.80
            guideline = "Tendencia bajista limpia. Asignación al 115% priorizando ventas cortas en zonas OTE."

        # 5. Régimen Neutro / Transición Estándar
        else:
            regime = MarketRegime.NEUTRAL
            multiplier = 1.00
            confidence = 0.70
            guideline = "Mercado en equilibrio o rotación inter-sesión. Asignación nominal 100% de riesgo."

        assessment = RegimeAssessment(
            regime=regime,
            confidence=confidence,
            risk_multiplier=multiplier,
            adx_avg=adx_mean,
            ker_avg=ker_mean,
            btc_htf_trend=btc_htf_trend,
            actionable_guideline=guideline
        )

        self.last_assessment = assessment
        vault.record_regime_state(
            regime=assessment.regime.value,
            risk_multiplier=assessment.risk_multiplier,
            confidence=assessment.confidence,
            details=assessment.to_dict()
        )

        logger.info(f"🧭 [REGIME AGENT] Régimen detectado: {assessment.regime.value} (x{assessment.risk_multiplier:.2f}) | {guideline}")
        return assessment

    def check_ml_health_and_trigger_retrain(self, drift_report: DriftReport, min_accuracy: float = 0.52) -> bool:
        """
        Evalúa el reporte del Drift Monitor y dispara el reentrenamiento condicional atómico si hay obsolescencia.
        """
        if not drift_report:
            return False

        if drift_report.drift_level == "SEVERE" or drift_report.alert_triggered or (drift_report.rolling_accuracy > 0 and drift_report.rolling_accuracy < 0.45):
            logger.warning(f"🚨 [REGIME AGENT] Obsolescencia de modelo detectada (PSI Max: {drift_report.psi_max:.3f}, Acc: {drift_report.rolling_accuracy:.2%}). Disparando SOP-61 Safe Auto-Retrain...")
            success, msg = safe_auto_retrain(min_accuracy=min_accuracy)
            logger.info(f"🧠 [REGIME AGENT] Resultado de auto-retrain condicional: {msg}")
            return success
        return False

    def format_telegram_regime_report(self, assessment: RegimeAssessment) -> str:
        """
        Genera el informe ejecutivo en Markdown para notificaciones en Telegram.
        """
        icon_map = {
            MarketRegime.BULL_EXPANSION: "🚀",
            MarketRegime.BEAR_EXPANSION: "📉",
            MarketRegime.CHOP_COMPRESSION: "🛡️",
            MarketRegime.HIGH_VOL_SHOCK: "⚡",
            MarketRegime.NEUTRAL: "⚖️"
        }
        icon = icon_map.get(assessment.regime, "🧭")
        return (
            f"{icon} *SLINGSHOT REGIME INTELLIGENCE BRIEFING*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• *Régimen Activo:* `{assessment.regime.value}`\n"
            f"• *Confianza Algorítmica:* `{assessment.confidence*100:.1f}%`\n"
            f"• *Multiplicador de Riesgo:* `x{assessment.risk_multiplier:.2f}`\n"
            f"• *Fuerza de Tendencia (ADX):* `{assessment.adx_avg:.1f}`\n"
            f"• *Eficiencia Kaufman (KER):* `{assessment.ker_avg:.3f}`\n"
            f"• *Sesgo Macro BTC HTF:* `{assessment.btc_htf_trend}`\n"
            f"───────────────────────\n"
            f"📋 *Directriz Táctica:*\n_{assessment.actionable_guideline}_\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━"
        )


# Instancia global del agente
regime_agent = SlingshotRegimeAgent()
