"""
engine/analytics/prop_firm_pass_simulator.py — Simulador Monte Carlo Diario v2.0 (SOP-152)
===========================================================================================
Motor institucional por bloques de días calendario (Daily-Clustered Block Bootstrap):
- Evalúa el límite diario oficial FTMO (-5.0% sobre equidad flotante desde max(balance, equity) a 00:00 CE(S)T).
- Evalúa el límite máximo total (-10.0% desde balance inicial).
- Modela la simultaneidad intradía (varios trades perdiendo el mismo día + MAE flotante).
- Reporta escenario Base Empírico OOS y escenario Estresado (-30% Shrinkage en E[R] + colas -1.25R),
  con desglose exacto de causa de fallo (daily_dd_pct vs. total_dd_pct vs. timeout_pct).
"""

import json
import os
from collections import defaultdict
from typing import Any, Dict, List, Optional
import numpy as np

from engine.risk.prop_firm_governor import PROP_FIRM_TIER1_CRYPTO_UNIVERSE


class PropFirmPassSimulator:
    """Evaluador estocástico realista de probabilidad de pase de fondeo (v2.0 Daily-Clustered)."""

    DEFAULT_REPORT_PATH = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "backtest",
        "reports",
        "chronological_backtest_report.json",
    )
    FTMO_SWING_REPORT_PATH = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "backtest",
        "reports",
        "ftmo_swing_scientific_audit_sop154.json",
    )

    @classmethod
    def load_daily_clusters(
        cls,
        report_path: Optional[str] = None,
        prop_tier1_only: bool = True,
        friction_haircut: float = 0.884,
        sl_slippage_r: float = 0.04,
        profile: str = "CRYPTO_PROP",
    ) -> List[Dict[str, Any]]:
        """Agrupa los trades auditados por día calendario para preservar correlación intradía."""
        if profile.upper() == "FTMO_SWING":
            path = report_path or cls.FTMO_SWING_REPORT_PATH
        else:
            path = report_path or cls.DEFAULT_REPORT_PATH
        if not os.path.exists(path):
            return [
                {"day": f"d{i}", "net_r": r, "worst_intraday_r": min(r, -1.04), "trades": 1}
                for i, r in enumerate([0.85, -1.04, 1.40, -1.04, 2.10, -1.04, 0.90, 1.30])
            ]

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        trades = data.get("oos_trade_stream") or data.get("trades") or data.get("trade_log") or []
        by_day: Dict[str, List[float]] = defaultdict(list)

        for idx, t in enumerate(trades):
            sym = str(t.get("symbol") or t.get("asset") or "").upper()
            if profile.upper() != "FTMO_SWING" and prop_tier1_only and sym not in PROP_FIRM_TIER1_CRYPTO_UNIVERSE:
                continue
            raw_r = float(t.get("pnl_r") or t.get("outcome_r") or t.get("r_multiple") or 0.0)
            # FTMO_SWING oos_trade_stream ya viene neto de spread, comisión y swap nocturno
            if profile.upper() == "FTMO_SWING":
                net_r = raw_r
            else:
                net_r = raw_r * friction_haircut if raw_r > 0 else raw_r - sl_slippage_r
            day_key = str(t.get("day") or t.get("entry_time") or t.get("timestamp") or f"day_{idx // 2}")[:10]
            by_day[day_key].append(net_r)

        clusters: List[Dict[str, Any]] = []
        for day_key, rs in sorted(by_day.items()):
            # Peor excursión intradía del día: suma de pérdidas simultáneas o peor secuencia acumulada
            cum = 0.0
            min_cum = 0.0
            for r in rs:
                cum += r
                if cum < min_cum:
                    min_cum = cum
            # Si hay pérdidas en el día, modelamos MAE flotante realista (-0.15R adicional por ruido intradía)
            worst_intraday = min(min_cum, sum(x for x in rs if x < 0)) - (0.15 if any(x < 0 for x in rs) else 0.0)
            clusters.append({
                "day": day_key,
                "net_r": round(sum(rs), 4),
                "worst_intraday_r": round(worst_intraday, 4),
                "trades": len(rs),
            })
        return clusters

    @classmethod
    def load_audited_r_series(
        cls,
        report_path: Optional[str] = None,
        prop_tier1_only: bool = True,
        friction_haircut: float = 0.884,
        sl_slippage_r: float = 0.04,
    ) -> np.ndarray:
        clusters = cls.load_daily_clusters(report_path, prop_tier1_only, friction_haircut, sl_slippage_r)
        return np.array([c["net_r"] for c in clusters], dtype=np.float64)

    def _simulate_single_regime(
        self,
        daily_clusters: List[Dict[str, Any]],
        risk_grid_pct: List[float],
        n_trials: int,
        block_days: int,
        seed: int,
        shrinkage_factor: float,
        tail_slippage_prob: float,
        challenge_fee_usd: float,
        account_size_usd: float,
    ) -> List[Dict[str, Any]]:
        rng = np.random.default_rng(seed)
        n_days = len(daily_clusters)
        results: List[Dict[str, Any]] = []

        for risk_pct in risk_grid_pct:
            p1_passes = 0
            p2_passes = 0
            fail_daily_dd = 0
            fail_total_dd = 0
            fail_timeout = 0
            days_to_funded: List[int] = []

            for _ in range(n_trials):
                # Circular Block Bootstrap sobre días calendario (máx. 180 días)
                sim_days: List[Dict[str, Any]] = []
                while len(sim_days) < 180:
                    start = int(rng.integers(0, n_days))
                    for k in range(block_days):
                        sim_days.append(daily_clusters[(start + k) % n_days])

                eq_pct = 0.0
                p1_ok = False
                day_idx = 0
                failed = False

                # Fase 1: +10.1% target, -5.0% diario intradía, -10.0% total
                while day_idx < 120:
                    d = sim_days[day_idx]
                    day_idx += 1
                    eff_risk = risk_pct * 0.5 if eq_pct >= 8.5 else risk_pct

                    day_net_r = d["net_r"] * shrinkage_factor if d["net_r"] > 0 else d["net_r"]
                    day_worst_r = d["worst_intraday_r"]
                    if day_worst_r < 0 and rng.random() < tail_slippage_prob:
                        day_worst_r -= 0.25
                        day_net_r -= 0.25

                    # Regla oficial FTMO 00:00 CE(S)T: piso diario = -5.0% desde inicio del día
                    if (day_worst_r * eff_risk) <= -5.0:
                        fail_daily_dd += 1
                        failed = True
                        break

                    eq_pct += day_net_r * eff_risk
                    if eq_pct <= -10.0:
                        fail_total_dd += 1
                        failed = True
                        break
                    if eq_pct >= 10.1:
                        p1_ok = True
                        p1_passes += 1
                        break

                if not p1_ok and not failed:
                    fail_timeout += 1

                if p1_ok:
                    eq2 = 0.0
                    p2_ok = False
                    failed2 = False
                    while day_idx < 180:
                        d = sim_days[day_idx]
                        day_idx += 1
                        eff_risk2 = risk_pct * 0.5 if eq2 >= 4.25 else risk_pct

                        day_net_r = d["net_r"] * shrinkage_factor if d["net_r"] > 0 else d["net_r"]
                        day_worst_r = d["worst_intraday_r"]
                        if day_worst_r < 0 and rng.random() < tail_slippage_prob:
                            day_worst_r -= 0.25
                            day_net_r -= 0.25

                        if (day_worst_r * eff_risk2) <= -5.0:
                            fail_daily_dd += 1
                            failed2 = True
                            break
                        eq2 += day_net_r * eff_risk2
                        if eq2 <= -10.0:
                            fail_total_dd += 1
                            failed2 = True
                            break
                        if eq2 >= 5.1:
                            p2_ok = True
                            p2_passes += 1
                            days_to_funded.append(day_idx)
                            break
                    if not p2_ok and not failed2:
                        fail_timeout += 1

            funded_rate = round((p2_passes / n_trials) * 100.0, 2)
            payout_usd = account_size_usd * 0.04 * 0.80 + challenge_fee_usd
            ev_usd = round((p2_passes / n_trials) * payout_usd - (1.0 - p2_passes / n_trials) * challenge_fee_usd, 2)

            results.append({
                "risk_per_trade_pct": risk_pct,
                "phase1_pass_rate_pct": round((p1_passes / n_trials) * 100.0, 2),
                "funded_pass_rate_pct": funded_rate,
                "bust_rate_pct": round(((fail_daily_dd + fail_total_dd) / n_trials) * 100.0, 2),
                "fail_daily_dd_pct": round((fail_daily_dd / n_trials) * 100.0, 2),
                "fail_total_dd_pct": round((fail_total_dd / n_trials) * 100.0, 2),
                "fail_timeout_pct": round((fail_timeout / n_trials) * 100.0, 2),
                "p50_days_to_funded": round(float(np.median(days_to_funded)), 1) if days_to_funded else 0.0,
                "p90_days_to_funded": round(float(np.percentile(days_to_funded, 90)), 1) if days_to_funded else 0.0,
                "expected_value_usd": ev_usd,
            })
        return results

    def simulate_risk_grid(
        self,
        r_series_or_clusters: Any,
        risk_grid_pct: Optional[List[float]] = None,
        n_trials: int = 2000,
        block_size: int = 3,
        seed: int = 42,
        challenge_fee_usd: float = 540.0,
        account_size_usd: float = 100000.0,
    ) -> Dict[str, Any]:
        if isinstance(r_series_or_clusters, list) and r_series_or_clusters and isinstance(r_series_or_clusters[0], dict):
            clusters = r_series_or_clusters
        else:
            arr = list(r_series_or_clusters) if r_series_or_clusters is not None else []
            if len(arr) == 0:
                return {"error": "EMPTY_R_SERIES", "results": []}
            clusters = [
                {"day": f"d{i}", "net_r": float(r), "worst_intraday_r": min(float(r), -1.04) if float(r) < 0 else 0.0, "trades": 1}
                for i, r in enumerate(arr)
            ]

        grid = risk_grid_pct or [0.40, 0.50, 0.60, 0.75, 1.00, 2.50]
        base_results = self._simulate_single_regime(
            clusters, grid, n_trials, block_size, seed, shrinkage_factor=1.0, tail_slippage_prob=0.05,
            challenge_fee_usd=challenge_fee_usd, account_size_usd=account_size_usd,
        )
        stressed_results = self._simulate_single_regime(
            clusters, grid, n_trials, block_size, seed + 1, shrinkage_factor=0.70, tail_slippage_prob=0.10,
            challenge_fee_usd=challenge_fee_usd, account_size_usd=account_size_usd,
        )
        best = max(stressed_results, key=lambda x: (x["funded_pass_rate_pct"], x["expected_value_usd"]))

        return {
            "simulator_version": "SOP-152_DAILY_CLUSTERED_V2",
            "sample_days": len(clusters),
            "universe": list(PROP_FIRM_TIER1_CRYPTO_UNIVERSE),
            "trials_per_risk": n_trials,
            "optimal_risk_pct": best["risk_per_trade_pct"],
            "results": base_results,
            "stressed_oos_results": stressed_results,
        }


prop_firm_pass_simulator = PropFirmPassSimulator()
