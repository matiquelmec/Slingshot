"""
engine/main_router.py — v5.7.155 Master Gold
=========================================================
SlingshotRouter: El Orquestador Maestro.

ANTES (v4.x): Arquitectura monolítica.
AHORA  (v5.4): Arquitectura desacoplada de alto rendimiento.

  MarketAnalyzer  → Capas 1-3 (S/R, Wyckoff, SMC, Fibonacci)
  SignalGatekeeper → 4 porteros institucionales en cadena
  build_base_result / enrich_signal → Despacho al Frontend

Mantiene 100% de compatibilidad con la interface pública anterior:
  router.process_market_data(df, asset, interval, ...)  → dict
"""
from __future__ import annotations
from engine.core.logger import logger

import pandas as pd
import time

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
        onchain_bias: str | None = None,
        heatmap: dict | None = None,
    ):
        """Actualiza el contexto del Jurado de Confluencia para el próximo ciclo."""
        if ml_projection        is not None: self._context.ml_projection        = ml_projection
        if session_data         is not None: self._context.session_data          = session_data
        if news_items           is not None: self._context.news_items            = news_items
        if economic_events      is not None: self._context.economic_events       = economic_events
        if liquidation_clusters is not None: self._context.liquidation_clusters  = liquidation_clusters
        if onchain_bias         is not None: self._context.onchain_bias          = onchain_bias
        if heatmap              is not None: self._context.heatmap               = heatmap

    # ── API pública: Pipeline Principal ──────────────────────────────────────

    def process_market_data(
        self,
        df: pd.DataFrame,
        asset: str = "BTCUSDT",
        interval: str = "15m",
        macro_levels=None,
        htf_bias=None,
        silent: bool = False,
        event_time_ms: int | None = None,
        heatmap: dict | None = None,
        context: GatekeeperContext | None = None,
    ) -> dict:
        """
        Pipeline principal: transforma velas OHLCV en señales institucionales.
        Optimización v5.7: Caché de análisis y procesamiento eficiente.
        """
        # ── Monitor de Latencia (Drift Monitor) ──────────────────────────────
        start_t = time.time()
        if event_time_ms:
            drift_ms = (start_t * 1000) - event_time_ms
            if drift_ms > 300:
                logger.warning(f"⚠️ [LATENCY] High Latency detectada en el router: {drift_ms:.2f}ms de drift")
        
        # [IDENTITY v6.8.4]
        if not silent:
            logger.info(f"🚦 [ROUTER_ENTRY] Processing asset: {asset}")

        # ── Fase 1: Análisis del Mercado (Capa 1-3) ──────────────────────────
        # Intentamos recuperar del cache si el timestamp no ha cambiado
        # Nota: En v5.7 usamos un hash ligero basado en el último timestamp
        market_map = self._analyzer.analyze(
            df=df,
            asset=asset,
            interval=interval,
            macro_levels=macro_levels,
            htf_bias=htf_bias,
            heatmap=heatmap,
            silent=silent
        )

        if heatmap: self._context.heatmap = heatmap # Inyección dinámica v5.7

        # ── Fase 2: Detección de Oportunidades SMC ───────────────────────────
        df_analyzed   = market_map.df_analyzed
        analyzed_df   = self._strategy.analyze(df_analyzed)
        opportunities = self._strategy.find_opportunities(analyzed_df, asset=asset)

        # Ordenar por timestamp descendente
        try:
            opportunities = sorted(opportunities, key=lambda x: x.get("timestamp", ""), reverse=True)
        except Exception:
            pass

        # ── Fase 3: Enriquecimiento de Riesgo (pre-Portero) ──────────────────
        enriched: list[dict] = []
        for sig in opportunities:
            sig["asset"] = asset  # [IDENTIDAD v6.8.1] Asegura filtrado diferenciado
            risk_data = self._risk.calculate_position(
                current_price=sig["price"],
                signal_type=sig.get("signal_type", "LONG"),
                market_regime=sig.get("regime", "RANGING"),
                key_levels=market_map.key_levels,
                smc_data=market_map.smc,
                atr_value=sig.get("atr_value", 0.0),
                asset=asset,
            )
            enriched.append(enrich_signal(sig, risk_data, interval))

        # ── Fase 4: Portero Institucional ────────────────────────────────────
        gate = self._gatekeeper.process(
            signals=enriched,
            df=analyzed_df,  # [FIX] Pasamos el DF analizado que contiene las columnas SMC
            smc_map=market_map.smc,
            key_levels=market_map.key_levels,
            interval=interval,
            htf_bias=htf_bias,
            context=context if context else self._context,
            silent=silent,
        )

        # ── Fase 5: Ensamblaje del Resultado Final ───────────────────────────
        result = build_base_result(market_map)
        result["signals"]         = gate.approved
        result["blocked_signals"] = gate.blocked

        # Inyectar info de sesgo macro en el diagnóstico
        result["diagnostic"]["pdl_swept"] = bool(self._context.session_data.get("pdl_swept", False))
        result["diagnostic"]["pdh_swept"] = bool(self._context.session_data.get("pdh_swept", False))

        # ── Fase 6: Log Institucional Post-Aprobación (OMEGA Logic) ──────────
        for approved_sig in gate.approved:
            # Re-generamos el log del bridge pero ahora que sabemos que está aprobada
            symbol = approved_sig.get("asset", asset)
            from engine.execution.ftmo_bridge import prepare_ftmo_order_package
            # Módulo DELTA: Preparamos el paquete fragmentado
            prepare_ftmo_order_package(approved_sig)
            
            logger.info(
                f"[ROUTER] ✅ Señal APROBADA | {approved_sig['type']} @ ${approved_sig['price']:.2f}"
                f" | Score: {approved_sig.get('confluence', {}).get('score', '?')}%"
                f" | Leverage: {approved_sig.get('leverage')}x"
            )

        # Monitor de ejecución local
        process_time = (time.time() - start_t) * 1000
        if process_time > 100: # Mas de 100ms es señal de fatiga en el analyzer
             logger.debug(f"⏱️ [ROUTER] {asset} procesado en {process_time:.2f}ms")

        return result
