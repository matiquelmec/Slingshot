"""
engine/analytics/quant_statistical_rigor.py — Primitivas Cuantitativas Nivel 10/10 (SOP-156)
===========================================================================================
Implementación determinista de estándares institucionales:
1. Deflated Sharpe Ratio (DSR) — Bailey & López de Prado.
2. Combinatorial Purged Cross-Validation CPCV(6,2) + PBO (15 trayectorias OOS con embargo).
3. Politis-Romano Stationary Bootstrap (bloques geométricos aleatorios).
4. Wald Sequential Probability Ratio Test (SPRT) válido trade-a-trade.
"""

import math
from itertools import combinations
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_ppf(p: float) -> float:
    """Aproximación racional de Acklam para la inversa de la normal estándar."""
    p = min(max(float(p), 1e-12), 1.0 - 1e-12)
    a = [-3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02,
         1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00]
    b = [-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02,
         6.680131188771972e01, -1.328068155288572e01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00,
         -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00,
         3.754408661907416e00]
    plow = 0.02425
    phigh = 1.0 - plow
    if p < plow:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
        )
    if p > phigh:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
        )
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (
        (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
    )


def compute_deflated_sharpe_ratio(
    returns: Sequence[float],
    num_trials: int = 1,
    trial_sharpe_std: Optional[float] = None,
) -> Dict[str, float]:
    """
    Calcula el Deflated Sharpe Ratio (DSR) por operación ajustado por:
    - Número de configuraciones probadas (num_trials).
    - Asimetría (skewness) y curtosis (kurtosis) empíricas.
    """
    arr = np.asarray(returns, dtype=np.float64)
    n = len(arr)
    if n < 5:
        return {"sr_per_trade": 0.0, "sr_benchmark": 0.0, "dsr": 0.5, "skew": 0.0, "kurtosis": 3.0}

    mean_r = float(np.mean(arr))
    std_r = float(np.std(arr, ddof=1))
    if std_r <= 1e-9:
        return {"sr_per_trade": 0.0, "sr_benchmark": 0.0, "dsr": 0.5, "skew": 0.0, "kurtosis": 3.0}

    sr = mean_r / std_r
    z = (arr - mean_r) / std_r
    skew = float(np.mean(z ** 3))
    kurt = float(np.mean(z ** 4))

    m = max(1, int(num_trials))
    if m == 1:
        sr0 = 0.0
    else:
        euler_gamma = 0.5772156649
        var_sr = (trial_sharpe_std ** 2) if (trial_sharpe_std is not None and trial_sharpe_std > 0) else (1.0 / max(n, 10))
        sr0 = math.sqrt(var_sr) * (
            (1.0 - euler_gamma) * _norm_ppf(1.0 - 1.0 / m)
            + euler_gamma * _norm_ppf(1.0 - 1.0 / (m * math.e))
        )

    denom_sq = max(1e-6, 1.0 - skew * sr + ((kurt - 1.0) / 4.0) * (sr ** 2))
    z_dsr = ((sr - sr0) * math.sqrt(n - 1)) / math.sqrt(denom_sq)
    dsr = _norm_cdf(z_dsr)
    return {
        "sr_per_trade": round(sr, 4),
        "sr_benchmark": round(sr0, 4),
        "dsr": round(dsr, 4),
        "skew": round(skew, 3),
        "kurtosis": round(kurt, 3),
    }


def run_cpcv_validation(
    returns_r: Sequence[float],
    n_splits: int = 6,
    k_test: int = 2,
    embargo_pct: float = 0.02,
) -> Dict[str, Any]:
    """
    Combinatorial Purged Cross-Validation CPCV(6,2) -> C(6,2) = 15 trayectorias OOS.
    Aplica embargo temporal entre bloques de entrenamiento y prueba.
    """
    arr = np.asarray(returns_r, dtype=np.float64)
    n = len(arr)
    if n < n_splits * 4:
        return {
            "n_folds": 0,
            "fold_positive_rate_pct": 0.0,
            "median_oos_expectancy_r": 0.0,
            "median_oos_pf": 0.0,
            "pbo_score": 1.0,
        }

    indices = np.array_split(np.arange(n), n_splits)
    embargo = max(1, int(n * embargo_pct))
    oos_expectancies: List[float] = []
    oos_pfs: List[float] = []
    overfit_flags = 0

    for test_groups in combinations(range(n_splits), k_test):
        test_mask = np.zeros(n, dtype=bool)
        for g in test_groups:
            test_mask[indices[g]] = True

        # Embargo alrededor de cada bloque de prueba
        train_mask = ~test_mask
        for g in test_groups:
            start_i = int(indices[g][0])
            end_i = int(indices[g][-1])
            lo = max(0, start_i - embargo)
            hi = min(n, end_i + embargo + 1)
            train_mask[lo:start_i] = False
            train_mask[end_i + 1:hi] = False

        test_r = arr[test_mask]
        train_r = arr[train_mask]
        if len(test_r) < 3 or len(train_r) < 3:
            continue

        mean_test = float(np.mean(test_r))
        mean_train = float(np.mean(train_r))
        gp = float(np.sum(test_r[test_r > 0]))
        gl = float(np.abs(np.sum(test_r[test_r < 0])))
        pf = (gp / gl) if gl > 1e-9 else (99.0 if gp > 0 else 0.0)

        oos_expectancies.append(mean_test)
        oos_pfs.append(pf)
        if mean_train > 0 and mean_test <= 0:
            overfit_flags += 1

    folds = len(oos_expectancies)
    if folds == 0:
        return {"n_folds": 0, "fold_positive_rate_pct": 0.0, "median_oos_expectancy_r": 0.0, "median_oos_pf": 0.0, "pbo_score": 1.0}

    pos_folds = sum(1 for x in oos_expectancies if x > 0)
    return {
        "n_folds": folds,
        "fold_positive_rate_pct": round((pos_folds / folds) * 100.0, 2),
        "median_oos_expectancy_r": round(float(np.median(oos_expectancies)), 4),
        "median_oos_pf": round(float(np.median(oos_pfs)), 2),
        "pbo_score": round(overfit_flags / folds, 4),
    }


def stationary_bootstrap_sample(
    items: Sequence[Any],
    target_len: int,
    mean_block_len: float = 5.0,
    rng: Optional[np.random.Generator] = None,
) -> List[Any]:
    """Politis-Romano Stationary Bootstrap con longitud de bloque geométrica aleatoria."""
    n = len(items)
    if n == 0 or target_len <= 0:
        return []
    gen = rng if rng is not None else np.random.default_rng(42)
    p_jump = min(1.0, max(0.01, 1.0 / float(mean_block_len)))
    out: List[Any] = []
    idx = int(gen.integers(0, n))
    for _ in range(target_len):
        out.append(items[idx])
        if gen.random() < p_jump:
            idx = int(gen.integers(0, n))
        else:
            idx = (idx + 1) % n
    return out


def compute_wald_sprt(
    returns_r: Sequence[float],
    mu0: float = 0.0,
    mu1: float = 0.25,
    sigma: float = 0.985,
    alpha: float = 0.05,
    beta: float = 0.10,
) -> Dict[str, Any]:
    """
    Sequential Probability Ratio Test (Wald SPRT) válido tras cada operación individual.
    H0: E[R] <= mu0 (sin edge) vs H1: E[R] >= mu1 (edge institucional).
    """
    upper = math.log((1.0 - beta) / max(alpha, 1e-9))
    lower = math.log(max(beta, 1e-9) / (1.0 - alpha))
    arr = np.asarray(returns_r, dtype=np.float64)
    if len(arr) == 0 or sigma <= 1e-9:
        return {
            "sprt_log_likelihood": 0.0,
            "sprt_upper_bound": round(upper, 4),
            "sprt_lower_bound": round(lower, 4),
            "sprt_decision": "CONTINUE_SAMPLING",
            "sprt_progress_pct": 0.0,
        }

    var = sigma ** 2
    ll_terms = ((mu1 - mu0) / var) * (arr - 0.5 * (mu0 + mu1))
    llr = float(np.sum(ll_terms))

    if llr >= upper:
        decision = "EDGE_CERTIFIED"
    elif llr <= lower:
        decision = "EDGE_DECAY_ALERT"
    else:
        decision = "CONTINUE_SAMPLING"

    span = max(upper - lower, 1e-9)
    progress = min(100.0, max(0.0, ((llr - lower) / span) * 100.0))
    return {
        "sprt_log_likelihood": round(llr, 4),
        "sprt_upper_bound": round(upper, 4),
        "sprt_lower_bound": round(lower, 4),
        "sprt_decision": decision,
        "sprt_progress_pct": round(progress, 1),
    }
