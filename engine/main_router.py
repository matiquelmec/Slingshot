"""
engine/main_router.py — Slingshot v4.1 Platinum
================================================
SlingshotRouter: El Orquestador Maestro.

ANTES (v4.0): 400 líneas mezclando análisis, riesgo y despacho.
AHORA  (v4.1): ~80 líneas. Delega cada responsabilidad a su módulo:

  MarketAnalyzer  → Capas 1-3 (S/R, Wyckoff, SMC, Fibonacci)
  SignalGatekeeper → 4 porteros institucionales en cadena
  build_base_result / enrich_signal → Despacho al Frontend

Mantiene 100% de compatibilidad con la interface pública anterior:
  router.process_market_data(df, asset, interval, ...)  → dict
"""
from __future__ import annotations

import pandas as pd

from engine.api.config import settings
from engine.indicators.macro import get_macro_context
from engine.risk.risk_manager import RiskManager
from engine.strategies.smc import SMCInstitutionalStrategy

from engine.router.analyzer import MarketAnalyzer
from engine.router.gatekeeper import SignalGatekeeper, GatekeeperContext
from engine.router.dispatcher import build_base_result, enrich_signal


class SlingshotRouter:
    """
    Orquestador principal del pipeline institucional.
    Coordina Análisis → Estrategia SMC → Enriquecimiento → Portero → Despacho.
    """

    def __init__(self):
        self._analyzer   = MarketAnalyzer()
        self._strategy   = SMCInstitutionalStrategy()
        self._risk       = RiskManager(
            account_balance=settings.ACCOUNT_BALANCE,
            base_risk_pct=settings.MAX_RISK_PCT,
        )
        self._gatekeeper = SignalGatekeeper(self._risk)

        # Contexto externo inyectado por el Orchestrator en cada ciclo
        self._context = GatekeeperContext()

    # ── API pública: Inyección de Contexto ───────────────────────────────────

    def set_context(
        self,
        ml_projection: dict | None = None,
        session_data:  dict | None = None,
        news_items:    list | None = None,
        economic_events: list | None = None,
        liquidation_clusters: list | None = None,
    ):
        """Actualiza el contexto del Jurado de Confluencia para el próximo ciclo."""
        if ml_projection        is not None: self._context.ml_projection        = ml_projection
        if session_data         is not None: self._context.session_data          = session_data
        if news_items           is not None: self._context.news_items            = news_items
        if economic_events      is not None: self._context.economic_events       = economic_events
        if liquidation_clusters is not None: self._context.liquidation_clusters  = liquidation_clusters

    # ── API pública: Pipeline Principal ──────────────────────────────────────

    def process_market_data(
        self,
        df: pd.DataFrame,
        asset: str = "BTCUSDT",
        interval: str = "15m",
        macro_levels=None,
        htf_bias=None,
        silent: bool = False,
    ) -> dict:
        """
        Pipeline principal: transforma velas OHLCV en señales institucionales.
        Interface pública idéntica a la versión v4.0 para compatibilidad total.
        """
        # ── Fase 1: Análisis del Mercado ─────────────────────────────────────
        market_map = self._analyzer.analyze(
            df=df,
            asset=asset,
            interval=interval,
            macro_levels=macro_levels,
            htf_bias=htf_bias,
        )

        # ── Fase 2: Detección de Oportunidades SMC ───────────────────────────
        df_analyzed   = market_map.df_analyzed
        analyzed_df   = self._strategy.analyze(df_analyzed)
        opportunities = self._strategy.find_opportunities(analyzed_df)

        # Ordenar por timestamp descendente
        try:
            opportunities = sorted(opportunities, key=lambda x: x.get("timestamp", ""), reverse=True)
        except Exception:
            pass

        # ── Fase 3: Enriquecimiento de Riesgo (pre-Portero) ──────────────────
        enriched: list[dict] = []
        for sig in opportunities:
            risk_data = self._risk.calculate_position(
                current_price=sig["price"],
                signal_type=sig.get("signal_type", "LONG"),
                market_regime=sig.get("regime", "RANGING"),
                key_levels=market_map.key_levels,
                smc_data=market_map.smc,
                atr_value=sig.get("atr_value", 0.0),
            )
            enriched.append(enrich_signal(sig, risk_data, interval))

        # ── Fase 4: Portero Institucional ────────────────────────────────────
        gate = self._gatekeeper.process(
            signals=enriched,
            df=df_analyzed,
            smc_map=market_map.smc,
            key_levels=market_map.key_levels,
            interval=interval,
            htf_bias=htf_bias,
            context=self._context,
            silent=silent,
        )

        # ── Fase 5: Ensamblaje del Resultado Final ───────────────────────────
        result = build_base_result(market_map)
        result["signals"]         = gate.approved
        result["blocked_signals"] = gate.blocked

        # Inyectar info de sesgo macro en el diagnóstico
        result["diagnostic"]["pdl_swept"] = bool(self._context.session_data.get("pdl_swept", False))
        result["diagnostic"]["pdh_swept"] = bool(self._context.session_data.get("pdh_swept", False))

        if gate.approved:
            last = gate.approved[-1]
            print(
                f"[ROUTER] ✅ Señal APROBADA | {last['type']} @ ${last['price']:.2f}"
                f" | Score: {last.get('confluence', {}).get('score', '?')}%"
                f" | Leverage: {last.get('leverage')}x"
            )

        return result
