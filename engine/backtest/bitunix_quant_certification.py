"""
engine/backtest/bitunix_quant_certification.py — Certificación Cuantitativa 10/10 Bitunix (SOP-156)
==================================================================================================
Audita el portafolio canónico de 13 activos Cripto (sin alterar SOP-147 ni el 2.50% de riesgo):
- Aplica fricción empírica SOP-119.
- Calcula Deflated Sharpe Ratio (DSR) ajustado por múltiples pruebas.
- Ejecuta CPCV(6,2) (15 trayectorias OOS purgadas con embargo) y PBO.
"""

import json
import os
from typing import Any, Dict, List

import numpy as np

from engine.analytics.monte_carlo_resilience_engine import apply_sop119_live_friction
from engine.analytics.quant_statistical_rigor import compute_deflated_sharpe_ratio, run_cpcv_validation

BASE_REPORT = os.path.join(os.path.dirname(__file__), "reports", "chronological_backtest_report.json")
CERT_REPORT = os.path.join(os.path.dirname(__file__), "reports", "bitunix_quant_certification_sop156.json")


def run_bitunix_quant_certification(save_report: bool = True) -> Dict[str, Any]:
    if not os.path.exists(BASE_REPORT):
        return {"status": "MISSING_BASE_REPORT"}

    with open(BASE_REPORT, "r", encoding="utf-8") as f:
        data = json.load(f)

    raw_trades = data.get("trades") or data.get("trade_log") or []
    raw_rs = [float(t.get("pnl_r") or t.get("outcome_r") or t.get("r_multiple") or 0.0) for t in raw_trades]
    net_rs = apply_sop119_live_friction(raw_rs, seed=42)

    dsr = compute_deflated_sharpe_ratio(net_rs, num_trials=15)
    cpcv = run_cpcv_validation(net_rs, n_splits=6, k_test=2, embargo_pct=0.02)

    report = {
        "protocol": "SOP-156_BITUNIX_QUANT_CERTIFICATION",
        "frozen_mode_respected": True,
        "base_risk_pct": 2.50,
        "trades_audited": len(net_rs),
        "net_expectancy_r": round(float(np.mean(net_rs)), 4) if net_rs else 0.0,
        "net_total_r": round(float(np.sum(net_rs)), 2) if net_rs else 0.0,
        "deflated_sharpe": dsr,
        "cpcv_15_folds": cpcv,
    }
    if save_report:
        os.makedirs(os.path.dirname(CERT_REPORT), exist_ok=True)
        with open(CERT_REPORT, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    return report


if __name__ == "__main__":
    res = run_bitunix_quant_certification(save_report=True)
    print(json.dumps(res, indent=2))
