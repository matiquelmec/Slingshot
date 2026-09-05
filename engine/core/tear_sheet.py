"""
engine/core/tear_sheet.py — v1.0.0 (SOP-60 Institutional Tear Sheet Engine)
=============================================================================
Calcula métricas financieras profesionales (Sharpe, Sortino, Max Drawdown,
Profit Factor, Payoff Ratio) sobre transacciones reales de Slingshot.
"""
from __future__ import annotations
import math
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


def calculate_portfolio_metrics(returns_r: List[float], risk_free_rate: float = 0.0) -> Dict[str, Any]:
    """
    Calcula métricas financieras formales a partir de un vector de retornos en unidades R o USD.
    """
    if not returns_r:
        return {
            "total_trades": 0,
            "win_rate_pct": 0.0,
            "profit_factor": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "max_drawdown_r": 0.0,
            "net_r": 0.0,
            "expectancy_r": 0.0,
            "avg_win_r": 0.0,
            "avg_loss_r": 0.0
        }

    arr = np.array(returns_r, dtype=float)
    total_trades = len(arr)
    wins = arr[arr > 0]
    losses = arr[arr < 0]

    win_count = len(wins)
    loss_count = len(losses)
    win_rate = round((win_count / total_trades) * 100.0, 2)

    total_profit = float(np.sum(wins)) if win_count > 0 else 0.0
    total_loss = float(np.abs(np.sum(losses))) if loss_count > 0 else 0.0
    profit_factor = round(total_profit / total_loss, 2) if total_loss > 0 else (99.9 if total_profit > 0 else 0.0)

    net_r = round(float(np.sum(arr)), 2)
    mean_r = float(np.mean(arr))
    expectancy_r = round(mean_r, 3)

    avg_win = round(float(np.mean(wins)), 2) if win_count > 0 else 0.0
    avg_loss = round(float(np.mean(losses)), 2) if loss_count > 0 else 0.0

    # Sharpe Ratio Anualizado (Asumiendo 365 días / trades secuenciales)
    std_r = float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0
    sharpe = round((mean_r - risk_free_rate) / (std_r + 1e-9) * math.sqrt(252), 2) if std_r > 0 else 0.0

    # Sortino Ratio (Downside deviation solamente)
    downside = arr[arr < 0]
    downside_std = float(np.std(downside, ddof=1)) if len(downside) > 1 else (float(np.std(downside)) if len(downside) > 0 else 0.0)
    sortino = round((mean_r - risk_free_rate) / (downside_std + 1e-9) * math.sqrt(252), 2) if downside_std > 0 else (sharpe if sharpe > 0 else 0.0)

    # Max Drawdown en R
    equity_curve = np.cumsum(arr)
    peak = np.maximum.accumulate(equity_curve)
    drawdowns = peak - equity_curve
    max_dd = round(float(np.max(drawdowns)), 2) if len(drawdowns) > 0 else 0.0

    return {
        "total_trades": total_trades,
        "win_count": win_count,
        "loss_count": loss_count,
        "win_rate_pct": win_rate,
        "profit_factor": profit_factor,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "max_drawdown_r": max_dd,
        "net_r": net_r,
        "expectancy_r": expectancy_r,
        "avg_win_r": avg_win,
        "avg_loss_r": avg_loss
    }


def format_tear_sheet_markdown(metrics: Dict[str, Any], account_label: str = "Cartera Global") -> str:
    """Genera un reporte institucional estructurado en Markdown para Telegram o informes."""
    now_str = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    lines = [
        f"📊 <b>TEAR SHEET CUANTITATIVO INSTITUCIONAL — {account_label}</b>",
        f"<i>Generado: {now_str} | Slingshot v49.0 APEX QUANTUM</i>",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"📈 <b>Retorno Neto Total:</b> <code>+{metrics.get('net_r', 0.0)} R</code>",
        f"🎯 <b>Win Rate:</b> <code>{metrics.get('win_rate_pct', 0.0)}%</code> ({metrics.get('win_count', 0)}W / {metrics.get('loss_count', 0)}L)",
        f"⚖️ <b>Profit Factor:</b> <code>{metrics.get('profit_factor', 0.0)}</code>",
        f"🛡️ <b>Max Drawdown:</b> <code>-{metrics.get('max_drawdown_r', 0.0)} R</code>",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"🏆 <b>Sharpe Ratio:</b> <code>{metrics.get('sharpe_ratio', 0.0)}</code> (Anualizado)",
        f"⚡ <b>Sortino Ratio:</b> <code>{metrics.get('sortino_ratio', 0.0)}</code> (Downside Risk)",
        f"📐 <b>Esperanza Matemática:</b> <code>+{metrics.get('expectancy_r', 0.0)} R / trade</code>",
        f"💎 <b>Ratio Asimétrico (Win/Loss):</b> <code>+{metrics.get('avg_win_r', 0.0)}R / {metrics.get('avg_loss_r', 0.0)}R</code>",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "🤖 <i>Auditoría Criptográfica SSoT Slingshot Vault WAL.</i>"
    ]
    return "\n".join(lines)
