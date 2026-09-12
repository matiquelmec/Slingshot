"""
engine/core/bayesian_confluence.py — Calibrador Bayesiano Dinámico de Confluencias (v53.0)
========================================================================================
Ajusta dinámicamente los pesos de la matriz de confluencias SMC en tiempo real
utilizando actualización bayesiana conjugada Beta-Binomial sobre los últimos N trades.

Modelo Matemático:
    Prior: Beta(alpha_0, beta_0) donde alpha_0 = 10, beta_0 = 10 (Priori neutral: 50% Win Rate)
    Likelihood: Binomial(n_trades, p) donde n_trades = wins + losses en ventana rodante.
    Posterior: Beta(alpha_0 + wins, beta_0 + losses)
    Esperanza Posterior: E[p] = (alpha_0 + wins) / (alpha_0 + beta_0 + wins + losses)
    Multiplicador: M_f = clamp(E[p] / 0.50, min_mult=0.50, max_mult=1.60)
    Peso Calibrado: W_f = round(W_base * M_f)
"""

import math
import threading
import time
from typing import Dict, Any, List, Optional, Tuple
from engine.core.logger import logger

# Pesos base canónicos de Slingshot v10.0 Apex Sovereign
DEFAULT_BASE_WEIGHTS: Dict[str, float] = {
    "narrative_weight": 15.0,
    "poi_weight": 40.0,
    "liq_weight": 20.0,
    "vol_weight": 15.0,
    "ml_weight": 10.0,
    "delta_weight": 15.0,
    "cvd_weight": 15.0,
    "vwap_weight": 15.0,
    "htf_weight": 15.0,
    "econ_weight": 20.0,
    "heatmap_weight": 20.0,
    "smt_weight": 15.0,
    "onchain_weight": 15.0,
    "yosh_weight": 15.0,
}

# Mapeo de factores legibles a claves canónicas de peso
CHECKLIST_TO_WEIGHT_KEY: Dict[str, str] = {
    "Narrativa SMC": "narrative_weight",
    "Zonas POI": "poi_weight",
    "Liquidez": "liq_weight",
    "Huella RVOL": "vol_weight",
    "Predicción IA": "ml_weight",
    "ML Meta-Labeling": "ml_weight",
    "Order Flow Delta": "delta_weight",
    "CVD Divergence": "cvd_weight",
    "Daily VWAP Anchor": "vwap_weight",
    "Tendencia 4H HTF": "htf_weight",
    "Macro": "econ_weight",
    "Contexto Macro": "econ_weight",
    "Neural Heatmap": "heatmap_weight",
    "SMT Divergence": "smt_weight",
    "On-Chain Sentinel": "onchain_weight",
    "Yosh Order Flow": "yosh_weight",
    "Yosh: Value Area": "yosh_weight",
    "Yosh: Extremo VA": "yosh_weight",
    "Yosh: Defensa LVN": "yosh_weight",
    "Yosh: Trampa LAF": "yosh_weight",
    "Yosh: Golden Window": "yosh_weight",
    "Golden Pocket": "poi_weight",
    "Apex Override": "vol_weight",
    "Apex Boost": "vol_weight",
}


class BayesianConfluenceCalibrator:
    """
    Calibrador bayesiano en memoria con persistencia transaccional SQLite WAL.
    Garantiza lecturas O(1) (<0.01ms) en el loop crítico de ejecución de señales.
    """

    _instance = None
    _singleton_lock = threading.Lock()

    def __new__(cls, vault: Optional[Any] = None, *args, **kwargs):
        if vault is not None:
            instance = super(BayesianConfluenceCalibrator, cls).__new__(cls)
            instance._initialized = False
            return instance

        with cls._singleton_lock:
            if cls._instance is None:
                cls._instance = super(BayesianConfluenceCalibrator, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(
        self,
        vault: Optional[Any] = None,
        alpha_prior: float = 10.0,
        beta_prior: float = 10.0,
        min_multiplier: float = 0.50,
        max_multiplier: float = 1.60,
        rolling_window: int = 50,
    ):
        if getattr(self, "_initialized", False):
            return

        self._vault = vault
        self.alpha_prior = alpha_prior
        self.beta_prior = beta_prior
        self.min_multiplier = min_multiplier
        self.max_multiplier = max_multiplier
        self.rolling_window = rolling_window

        self._lock = threading.RLock()
        self._base_weights: Dict[str, float] = dict(DEFAULT_BASE_WEIGHTS)
        self._calibrated_weights: Dict[str, float] = dict(DEFAULT_BASE_WEIGHTS)
        self._factor_stats: Dict[str, Dict[str, Any]] = {}

        for key, base_w in self._base_weights.items():
            self._factor_stats[key] = {
                "base_weight": base_w,
                "calibrated_weight": base_w,
                "wins": 0,
                "losses": 0,
                "posterior_win_rate": 0.50,
                "multiplier": 1.0,
                "sample_size": 0,
            }

        self._initialized = True
        self._sync_with_vault()

    def get_vault(self):
        """Retorna la bóveda de persistencia activa (inyectada o global)."""
        if self._vault is not None:
            return self._vault
        from engine.core.vault import vault
        return vault

    def _sync_with_vault(self):
        """Carga los pesos guardados previamente en SQLite si existen."""
        try:
            v = self.get_vault()
            saved_weights = v.load_factor_weights()
            if saved_weights:
                with self._lock:
                    for k, w in saved_weights.items():
                        if k in self._calibrated_weights:
                            self._calibrated_weights[k] = float(w)
                            if k in self._factor_stats:
                                self._factor_stats[k]["calibrated_weight"] = float(w)
                logger.info(f"🏛️ [BAYESIAN CALIBRATOR] {len(saved_weights)} pesos cargados desde SQLite WAL.")
        except Exception as e:
            logger.debug(f"[BAYESIAN CALIBRATOR] Inicio en blanco o vault no disponible: {e}")

    def get_weight(self, factor_name: str, default: Optional[float] = None) -> float:
        """
        Retorna el peso calibrado actual para un factor.
        Acceso ultra-rápido en memoria O(1) (< 0.005 ms).
        """
        key = CHECKLIST_TO_WEIGHT_KEY.get(factor_name, factor_name)
        with self._lock:
            if key in self._calibrated_weights:
                return self._calibrated_weights[key]
            if default is not None:
                return float(default)
            return self._base_weights.get(key, 15.0)

    def get_all_weights(self) -> Dict[str, float]:
        """Retorna una copia de todos los pesos calibrados activos."""
        with self._lock:
            return dict(self._calibrated_weights)

    def get_factor_stats(self) -> Dict[str, Dict[str, Any]]:
        """Retorna estadísticas cuantitativas de los factores para telemetría y UI."""
        with self._lock:
            return {k: dict(v) for k, v in self._factor_stats.items()}

    def record_trade_attribution(
        self,
        trade_id: str,
        symbol: str,
        active_checklist: List[Dict[str, Any]],
        is_win: bool,
        pnl_r: float,
    ) -> Dict[str, Any]:
        """
        Atribuye el resultado de un trade a los factores de confluencia presentes.
        Actualiza la distribución posterior Beta-Binomial y recalibra los pesos.
        """
        confirmed_factors = set()
        for item in active_checklist:
            status = str(item.get("status", "")).upper()
            factor_raw = item.get("factor", "")
            if status in ("CONFIRMADO", "ELITE", "ALFA_GOLDEN", "ACTIVO", "INSTITUCIONAL", "FAVORABLE"):
                w_key = CHECKLIST_TO_WEIGHT_KEY.get(factor_raw)
                if w_key:
                    confirmed_factors.add(w_key)

        # Registrar en la base de datos persistente SQLite WAL
        try:
            v = self.get_vault()
            v.record_factor_attributions(
                trade_id=str(trade_id),
                symbol=symbol,
                confirmed_factors=list(confirmed_factors),
                unconfirmed_factors=[k for k in self._base_weights.keys() if k not in confirmed_factors],
                is_win=is_win,
                pnl_r=float(pnl_r),
            )
        except Exception as vault_err:
            logger.error(f"[BAYESIAN CALIBRATOR] Error guardando atribución en Vault: {vault_err}")

        # Recalcular pesos dinámicos en memoria
        return self.recalibrate()

    def recalibrate(self) -> Dict[str, float]:
        """
        Recalcula los pesos bayesianos usando los datos más recientes de la base de datos.
        """
        try:
            v = self.get_vault()
            stats_from_db = v.get_factor_rolling_stats(rolling_window=self.rolling_window)
        except Exception as e:
            logger.debug(f"[BAYESIAN CALIBRATOR] Fallback a estadísticas locales: {e}")
            stats_from_db = {}

        new_weights = {}
        updates_to_persist = []

        with self._lock:
            for key, base_w in self._base_weights.items():
                db_stat = stats_from_db.get(key, {})
                wins = int(db_stat.get("wins", self._factor_stats[key]["wins"]))
                losses = int(db_stat.get("losses", self._factor_stats[key]["losses"]))
                sample_size = wins + losses

                # Cálculo de la esperanza posterior Beta-Binomial
                alpha_post = self.alpha_prior + wins
                beta_post = self.beta_prior + losses
                posterior_win_rate = alpha_post / (alpha_post + beta_post)

                # Multiplicador adaptativo relativo a la base neutral (0.50)
                raw_multiplier = posterior_win_rate / 0.50
                clamped_multiplier = max(self.min_multiplier, min(self.max_multiplier, raw_multiplier))

                # Peso calibrado redondeado a entero
                calibrated_w = round(base_w * clamped_multiplier)

                self._calibrated_weights[key] = float(calibrated_w)
                self._factor_stats[key] = {
                    "base_weight": base_w,
                    "calibrated_weight": float(calibrated_w),
                    "wins": wins,
                    "losses": losses,
                    "posterior_win_rate": round(posterior_win_rate, 4),
                    "multiplier": round(clamped_multiplier, 3),
                    "sample_size": sample_size,
                }
                new_weights[key] = float(calibrated_w)

                updates_to_persist.append({
                    "factor_name": key,
                    "base_weight": base_w,
                    "calibrated_weight": float(calibrated_w),
                    "win_rate": round(posterior_win_rate, 4),
                    "wins": wins,
                    "losses": losses,
                    "sample_size": sample_size,
                })

        # Persistir pesos en SQLite WAL de forma asíncrona/segura
        try:
            v = self.get_vault()
            v.save_factor_weights(updates_to_persist)
        except Exception as save_err:
            logger.debug(f"[BAYESIAN CALIBRATOR] Error persistiendo pesos en Vault: {save_err}")

        logger.info(f"🔮 [BAYESIAN CALIBRATOR] Calibración completada: {len(new_weights)} factores actualizados.")
        return new_weights


# Instancia Singleton Global
bayesian_calibrator = BayesianConfluenceCalibrator()
