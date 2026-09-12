"""
engine/risk/hrp_allocator.py — Hierarchical Risk Parity (HRP) Portfolio Allocator
==================================================================================
Implementación matemática de Hierarchical Risk Parity (Marcos López de Prado).
Supera la optimización de Markowitz eliminando la necesidad de invertir la matriz de covarianza.

Etapas:
1. Tree Clustering: Matriz de distancias d_ij = sqrt(0.5 * (1 - rho_ij)) y enlace jerárquico.
2. Quasi-Diagonalization: Reordenamiento matricial para agrupar activos por similitud de covarianza.
3. Recursive Bisection: Asignación descendente de riesgo por varianza inversa de sub-clusters.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any
from scipy.cluster.hierarchy import linkage, to_tree
from scipy.spatial.distance import squareform

from engine.core.logger import logger


class HierarchicalRiskParityAllocator:
    """
    Optimizador Cuantitativo de Cartera Multi-Activo HRP.
    Distribuye el riesgo entre Cripto (Bitunix) y TradFi (FTMO/Metales/Índices/Forex).
    """

    def __init__(self, min_weight: float = 0.02, max_weight: float = 0.40):
        self.min_weight = min_weight
        self.max_weight = max_weight

    def compute_hrp_weights(self, returns_df: pd.DataFrame) -> Dict[str, float]:
        """
        Calcula las ponderaciones HRP a partir de una matriz de retornos periódicos.
        Si hay activos insuficientes (< 2) o datos vacíos, retorna ponderación equitativa.
        """
        if returns_df.empty or returns_df.shape[1] < 2 or len(returns_df) < 5:
            cols = list(returns_df.columns) if not returns_df.empty else []
            if not cols:
                return {}
            eq = round(1.0 / len(cols), 4)
            return {c: eq for c in cols}

        # Sanitizar valores NaN o infinitos
        clean_df = returns_df.replace([np.inf, -np.inf], np.nan).fillna(0.0)

        # 1. Matriz de Correlación y Covarianza
        corr = clean_df.corr().fillna(0.0).values
        cov = clean_df.cov().fillna(0.0).values
        assets = list(clean_df.columns)

        # Asegurar diagonal unitaria en correlación
        np.fill_diagonal(corr, 1.0)

        # 2. Matriz de Distancia de Correlación: d_ij = sqrt(0.5 * (1 - rho_ij))
        dist = np.sqrt(np.clip(0.5 * (1.0 - corr), 0.0, 1.0))
        np.fill_diagonal(dist, 0.0)

        # 3. Tree Clustering Jerárquico
        try:
            condensed_dist = squareform(dist, checks=False)
            link = linkage(condensed_dist, method="single")
            sorted_indices = self._get_quasi_diag(link)
            sorted_assets = [assets[i] for i in sorted_indices]
        except Exception as e:
            logger.debug(f"[HRP] Fallback en clustering jerárquico: {e}")
            eq = round(1.0 / len(assets), 4)
            return {c: eq for c in assets}

        # 4. Recursive Bisection (Bisección Recursiva)
        sorted_cov = clean_df[sorted_assets].cov().values
        weights_series = pd.Series(1.0, index=sorted_assets)
        cluster_items = [sorted_assets]

        while len(cluster_items) > 0:
            cluster_items = [
                i[j:k]
                for i in cluster_items
                for j, k in ((0, len(i) // 2), (len(i) // 2, len(i)))
                if len(i) > 1
            ]
            for i in range(0, len(cluster_items), 2):
                cluster_left = cluster_items[i]
                cluster_right = cluster_items[i + 1]

                var_left = self._get_cluster_variance(clean_df[cluster_left].cov().values)
                var_right = self._get_cluster_variance(clean_df[cluster_right].cov().values)

                total_var = var_left + var_right
                if total_var > 1e-9:
                    alpha = 1.0 - (var_left / total_var)
                else:
                    alpha = 0.5

                weights_series[cluster_left] *= alpha
                weights_series[cluster_right] *= (1.0 - alpha)

        # 5. Aplicar Clamps de Diversificación y Normalizar a Suma 1.0
        clamped = weights_series.clip(lower=self.min_weight, upper=self.max_weight)
        normalized = clamped / clamped.sum()

        result = {k: round(float(v), 4) for k, v in normalized.items()}
        logger.info(f"⚖️ [HRP ALLOCATOR] Ponderaciones calculadas para {len(result)} activos.")
        return result

    def calculate_trade_risk_usd(
        self,
        symbol: str,
        base_risk_usd: float,
        hrp_weights: Dict[str, float]
    ) -> float:
        """
        Modula el riesgo en dólares de un trade según la ponderación HRP del activo.
        """
        sym = symbol.upper()
        weight = hrp_weights.get(sym)
        if weight is None:
            # Buscar por prefijo base (ej. BTC de BTCUSDT)
            for k, w in hrp_weights.items():
                if sym.startswith(k) or k.startswith(sym):
                    weight = w
                    break

        if weight is None or len(hrp_weights) == 0:
            return round(base_risk_usd, 2)

        mean_weight = 1.0 / len(hrp_weights)
        # Multiplicador entre 0.60x y 1.40x centrado en la media del portafolio
        mult = np.clip(weight / (mean_weight + 1e-9), 0.60, 1.40)
        return round(base_risk_usd * mult, 2)

    def _get_quasi_diag(self, link: np.ndarray) -> List[int]:
        """Ordena los índices de activos para quasi-diagonalizar la covarianza."""
        link = link.astype(int)
        num_items = link[-1, 3]
        tree = to_tree(link, rd=False)
        return self._traverse_tree(tree)

    def _traverse_tree(self, node) -> List[int]:
        if node.is_leaf():
            return [node.id]
        return self._traverse_tree(node.left) + self._traverse_tree(node.right)

    def _get_cluster_variance(self, cov: np.ndarray) -> float:
        """Calcula la varianza total de un cluster con ponderación de varianza inversa."""
        diag_inv = 1.0 / np.diag(cov)
        diag_inv = np.nan_to_num(diag_inv, nan=1.0, posinf=1.0, neginf=1.0)
        w = diag_inv / np.sum(diag_inv)
        return float(np.dot(np.dot(w.T, cov), w))


hrp_allocator = HierarchicalRiskParityAllocator()
