"""
engine/workers/asset_incubator.py
=================================
MÓDULO INSTITUCIONAL DE INCUBACIÓN Y ROTACIÓN TRIMESTRAL DE ACTIVOS (SSoT v60.0)

Gobernanza bajo AGENTS.md & BLUEPRINT_2026.md:
1. SSoT Universe Alignment: Evalúa la salud estadística del Universo Canónico Auditado (13 activos).
2. Protocolo de Auditoría Trimestral (60 días / 500 operaciones):
   - Filtro de Liquidez: Volumen 24h >= $50M y Spread medio <= 0.08%.
   - Filtro de Eficiencia: Sharpe Ratio >= 1.80 y Expectativa Matemática > 0.20R/trade.
   - Filtro de Drawdown: Profit Factor >= 1.30 y Max Drawdown <= 3.5R.
3. Generación de Alertas de Reemplazo y Promoción:
   - Activos degradados persistentes -> INCUBATION_ALERT: REPLACEMENT_RECOMMENDED.
   - Activos candidatos externos en simulación -> INCUBATION_ALERT: PROMOTION_CANDIDATE.
"""

import math
from typing import Dict, List, Any, Optional
from loguru import logger

CANONICAL_AUDITED_UNIVERSE = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "FETUSDT",
    "INJUSDT", "NEARUSDT", "SUIUSDT", "ATOMUSDT", "TIAUSDT",
    "LINKUSDT", "XRPUSDT", "XAUUSDT"
]

PRUNED_EXCLUDED_ASSETS = ["RENDERUSDT", "AVAXUSDT", "RENDER", "AVAX"]


class AssetIncubator:
    """
    Motor cuantitativo de evaluación continua e incubación de activos.
    """

    MIN_VOLUME_24H_USD = 50_000_000.0  # $50M mínimo para evitar slippage
    MAX_SPREAD_PCT = 0.08               # 0.08% spread máximo institucional
    MIN_SHARPE_RATIO = 1.80             # Sharpe ratio mínimo rodante a 60 días
    MIN_EXPECTANCY_R = 0.20             # +0.20R promedio por operación
    MIN_PROFIT_FACTOR = 1.30            # Profit factor de supervivencia
    MAX_DRAWDOWN_R = 3.50               # Máximo drawdown histórico tolerable en R

    def __init__(self, canonical_universe: Optional[List[str]] = None):
        self.canonical_universe = list(canonical_universe or CANONICAL_AUDITED_UNIVERSE)
        self.pruned_assets = list(PRUNED_EXCLUDED_ASSETS)

    def evaluate_asset_health(
        self,
        symbol: str,
        trades: List[Dict[str, Any]],
        volume_24h_usd: float = 100_000_000.0,
        spread_pct: float = 0.04
    ) -> Dict[str, Any]:
        """
        Evalúa el rendimiento de un activo en una muestra de operaciones cerradas.
        """
        sym = (symbol or "").replace("/", "").upper()
        if not sym.endswith("USDT") and not sym in ["XAUUSDT", "PAXGUSDT"]:
            sym = f"{sym}USDT"

        asset_trades = [
            t for t in trades
            if str(t.get("asset") or t.get("symbol") or "").replace("/", "").upper() in (sym, sym.replace("USDT", ""))
        ]

        total_trades = len(asset_trades)
        if total_trades == 0:
            return {
                "asset": sym,
                "status": "INSUFFICIENT_DATA",
                "total_trades": 0,
                "profit_factor": 0.0,
                "sharpe_ratio": 0.0,
                "expectancy_r": 0.0,
                "net_r": 0.0,
                "max_drawdown_r": 0.0,
                "liquidity_passed": volume_24h_usd >= self.MIN_VOLUME_24H_USD and spread_pct <= self.MAX_SPREAD_PCT,
                "recommendation": "GATHERING_TELEMETRY"
            }

        outcomes_r: List[float] = []
        for t in asset_trades:
            # Soporta tanto pnl_r como outcome_r o r_multiples
            r_val = float(t.get("pnl_r") or t.get("outcome_r") or t.get("r_multiple") or 0.0)
            outcomes_r.append(r_val)

        wins = [r for r in outcomes_r if r > 0]
        losses = [r for r in outcomes_r if r < 0]
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        net_r = round(sum(outcomes_r), 4)

        win_rate = round(len(wins) / total_trades, 4) if total_trades > 0 else 0.0
        profit_factor = round(gross_profit / gross_loss, 4) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)
        expectancy_r = round(net_r / total_trades, 4) if total_trades > 0 else 0.0

        # Cálculo de Sharpe rodante simplificado sobre retornos en R
        mean_r = net_r / total_trades if total_trades > 0 else 0.0
        variance = sum((r - mean_r) ** 2 for r in outcomes_r) / total_trades if total_trades > 1 else 0.0001
        std_r = math.sqrt(variance)
        sharpe_ratio = round((mean_r / std_r) * math.sqrt(252), 2) if std_r > 0 else 0.0

        # Cálculo de Max Drawdown en R
        peak_equity = 0.0
        current_equity = 0.0
        max_drawdown_r = 0.0
        for r in outcomes_r:
            current_equity += r
            if current_equity > peak_equity:
                peak_equity = current_equity
            dd = peak_equity - current_equity
            if dd > max_drawdown_r:
                max_drawdown_r = dd

        max_drawdown_r = round(max_drawdown_r, 4)
        liquidity_ok = volume_24h_usd >= self.MIN_VOLUME_24H_USD and spread_pct <= self.MAX_SPREAD_PCT

        # Diagnóstico y Clasificación Institucional
        is_pruned = sym in self.pruned_assets or sym.replace("USDT", "") in self.pruned_assets
        is_canonical = sym in self.canonical_universe or sym.replace("USDT", "") in self.canonical_universe

        if is_pruned:
            status = "PRUNED_VETOED"
            recommendation = "PERMANENT_EXCLUSION"
        elif not liquidity_ok:
            status = "ILLIQUID_RISK"
            recommendation = "REPLACEMENT_RECOMMENDED"
        elif total_trades >= 30 and (profit_factor < self.MIN_PROFIT_FACTOR or max_drawdown_r > self.MAX_DRAWDOWN_R):
            status = "UNDERPERFORMING"
            recommendation = "REPLACEMENT_RECOMMENDED"
        elif total_trades >= 30 and sharpe_ratio >= self.MIN_SHARPE_RATIO and expectancy_r >= self.MIN_EXPECTANCY_R:
            status = "HEALTHY_LEADER" if is_canonical else "PROMOTION_CANDIDATE"
            recommendation = "MAINTAIN_CAPITAL" if is_canonical else "AUDIT_FOR_INCLUSION"
        else:
            status = "CORE_STABLE"
            recommendation = "MONITOR_CONTINUED"

        return {
            "asset": sym,
            "is_canonical": is_canonical,
            "status": status,
            "total_trades": total_trades,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "sharpe_ratio": sharpe_ratio,
            "expectancy_r": expectancy_r,
            "net_r": net_r,
            "max_drawdown_r": max_drawdown_r,
            "liquidity_passed": liquidity_ok,
            "volume_24h_usd": volume_24h_usd,
            "spread_pct": spread_pct,
            "recommendation": recommendation
        }

    def run_quarterly_audit(
        self,
        trades: List[Dict[str, Any]],
        market_stats: Optional[Dict[str, Dict[str, float]]] = None
    ) -> Dict[str, Any]:
        """
        Ejecuta la auditoría integral de todos los activos del universo canónico
        y activos candidatos monitoreados.
        """
        stats_map = market_stats or {}
        audit_results: List[Dict[str, Any]] = []

        for asset in self.canonical_universe:
            sym_stats = stats_map.get(asset, {})
            vol = float(sym_stats.get("volume_24h", 120_000_000.0))
            spread = float(sym_stats.get("spread_pct", 0.03))

            report = self.evaluate_asset_health(
                symbol=asset,
                trades=trades,
                volume_24h_usd=vol,
                spread_pct=spread
            )
            audit_results.append(report)

        # Ordenar por Sharpe Ratio y Net R
        audit_results.sort(key=lambda x: (x["sharpe_ratio"], x["net_r"]), reverse=True)

        leaders = [r for r in audit_results if r["status"] == "HEALTHY_LEADER"]
        underperformers = [r for r in audit_results if r["status"] == "UNDERPERFORMING" or r["recommendation"] == "REPLACEMENT_RECOMMENDED"]

        return {
            "timestamp_audit": "2026-Q4-AUDIT",
            "total_assets_audited": len(audit_results),
            "healthy_leaders_count": len(leaders),
            "underperformers_count": len(underperformers),
            "results": audit_results,
            "action_required": len(underperformers) > 0,
            "replacement_recommendations": [u["asset"] for u in underperformers]
        }
