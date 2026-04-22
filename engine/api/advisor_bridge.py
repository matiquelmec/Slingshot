"""
engine/api/advisor_bridge.py — v6.0.1 (Extraído de ws_manager.py)
=========================================================
Responsabilidad: Lógica de orquestación del LLM Advisor (Ollama)
                 y actualización del Ghost Data institucional.

Extraído del SymbolBroadcaster como parte del refactor ISS-011.
Antes vivía en ws_manager.py como métodos privados:
  _emit_advisor()        → AdvisorBridge.emit()
  _get_tactical_hash()   → AdvisorBridge.get_tactical_hash()
  _refresh_ghost()       → AdvisorBridge.refresh_ghost()

Módulos equivalentes ya extraídos:
  registry.py        — BroadcasterRegistry
  json_utils.py      — sanitize_for_json
  signal_handler.py  — Filtrado + persistencia de señales
  advisor_bridge.py  — (ESTE) LLM Advisor + Ghost Data
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from engine.core.logger import logger
from engine.api.json_utils import sanitize_for_json
from engine.indicators.ghost_data import (
    get_ghost_state,
    fetch_funding_rate,
    compute_symbol_ghost,
)
from engine.api.advisor import generate_tactical_advice
from engine.api.advisor import check_ollama_status

if TYPE_CHECKING:
    pass


class AdvisorBridge:
    """
    Encapsula toda la inteligencia artificial del SymbolBroadcaster:

      - `emit()`           → Llama al LLM (Ollama) con Gatekeeping cognitivo y caché semántica.
      - `refresh_ghost()`  → Obtiene Funding/Bias macro y calcula el system_verdict unificado.
      - `get_tactical_hash()` → MD5 estable del contexto táctico para caché semántica.

    Depende de la referencia al broadcaster padre ÚNICAMENTE para:
      - `_broadcast()` — enviar mensajes al frontend.
      - `_store`       — leer/guardar datos en MemoryStore.
      - `latest_price` — precio live para inyectar antes de enviar al LLM.
      - `_live_rvol`   — RVOL del Fast Path para el Advisor.
      - `_last_ml`     — última proyección ML.
      - `_last_onchain`— datos on-chain.
    """

    def __init__(self, symbol: str, interval: str, broadcaster_ref):
        """
        Args:
            symbol:          Ej. "BTCUSDT"
            interval:        Ej. "15m"
            broadcaster_ref: Referencia al SymbolBroadcaster padre.
        """
        self._symbol   = symbol.upper()
        self._interval = interval
        self._bc       = broadcaster_ref

        self._last_advisor_obj:    Optional[dict] = None
        self._last_tactical_hash:  Optional[str]  = None
        self._advisor_task:        Optional[asyncio.Task] = None

    # ── API Pública ───────────────────────────────────────────────────────────

    def get_tactical_hash(self, tactical: dict) -> str:
        """
        MD5 estable del estado táctico (excluye datos volátiles como candles/precio).
        Usado para la caché semántica: si el contexto no cambió, reutilizamos el análisis.
        """
        stable_keys = {
            "market_regime", "active_strategy", "macro_bias",
            "htf_bias", "smc", "diagnostic", "key_levels"
        }
        state     = {k: v for k, v in tactical.items() if k in stable_keys}
        state_str = json.dumps(state, sort_keys=True, default=str)
        return hashlib.md5(state_str.encode()).hexdigest()

    async def refresh_ghost(self, global_ghost=None):
        """
        Refresca Ghost Data (Funding específico + contexto global) y broadcast.

        Flujo:
          1. Obtener Fear & Greed + Dominancia (global_ghost o fetch fresco)
          2. Obtener Funding del símbolo en tiempo real
          3. Calcular Bias híbrido (compute_symbol_ghost)
          4. Calcular system_verdict unificado (Macro + ML)
          5. Broadcast → ghost_update
        """
        try:
            if not global_ghost:
                global_ghost = get_ghost_state()

            local_funding = await fetch_funding_rate(self._symbol)
            ghost         = compute_symbol_ghost(global_ghost, self._symbol, local_funding)

            # ── System Verdict Unificado (v5.7.155 Master Gold) ──────────────
            # Reconcilia Macro (Ghost) + ML en un veredicto único.
            # Contradicción → STAND_BY. Evita señales conflictivas en el frontend.
            ml_dir = (self._bc._last_ml or {}).get("direction", "NEUTRAL")
            ml_normalized = (
                "BULLISH" if ml_dir == "ALCISTA"
                else ("BEARISH" if ml_dir == "BAJISTA" else "NEUTRAL")
            )

            macro_dir     = ghost.macro_bias  # BULLISH / BEARISH / BLOCK_LONGS / BLOCK_SHORTS / NEUTRAL
            macro_bullish = macro_dir in ("BULLISH", "BLOCK_SHORTS")
            macro_bearish = macro_dir in ("BEARISH",  "BLOCK_LONGS")
            ml_bullish    = ml_normalized == "BULLISH"
            ml_bearish    = ml_normalized == "BEARISH"

            if   macro_bullish and ml_bullish:  system_verdict = "BULLISH"
            elif macro_bearish and ml_bearish:  system_verdict = "BEARISH"
            elif (macro_bullish and ml_bearish) or (macro_bearish and ml_bullish):
                                                system_verdict = "STAND_BY"
            else:                               system_verdict = "NEUTRAL"

            await self._bc._broadcast({"type": "ghost_update", "data": {
                "symbol":            self._symbol,
                "fear_greed_value":  ghost.fear_greed_value,
                "fear_greed_label":  ghost.fear_greed_label,
                "btc_dominance":     ghost.btc_dominance,
                "funding_rate":      ghost.funding_rate,
                "funding_symbol":    ghost.funding_symbol,
                "macro_bias":        ghost.macro_bias,
                "block_longs":       ghost.block_longs,
                "block_shorts":      ghost.block_shorts,
                "reason":            ghost.reason,
                "last_updated":      ghost.last_updated,
                "dxy_trend":         ghost.dxy_trend,
                "dxy_price":         ghost.dxy_price,
                "nasdaq_trend":      ghost.nasdaq_trend,
                "nasdaq_change_pct": ghost.nasdaq_change_pct,
                "risk_appetite":     ghost.risk_appetite,
                "system_verdict":    system_verdict,
            }})
        except Exception as e:
            logger.error(f"[ADVISOR_BRIDGE] {self._symbol}:{self._interval} → Ghost refresh error: {e}")

    async def emit(self, tactical: dict, session_state: dict, is_absorption_alert: bool = False):
        """
        Orquesta la llamada al LLM Advisor con:
          - Inyección de datos LIVE (precio + RVOL del Fast Path)
          - Capitán de activo (solo el intervalo 15m dispara el análisis)
          - Caché semántica MD5 (reutiliza si el contexto no cambió)
          - Gatekeeping cognitivo (bypass si score < 70 y régimen neutral)
          - Timeout de 60s con manejo elegante
          - Cancelación de tarea previa si llega nueva petición
        """
        bc = self._bc

        # ── 1. Inyección LIVE (precio + RVOL Fast Path) ───────────────────────
        # El tactical es un snapshot del momento del cierre de vela.
        # Si Ollama tarda 30-60s, el precio puede haber movido $500-$900.
        live_overrides: dict = {}
        if bc.latest_price and bc.latest_price > 0:
            live_overrides["current_price"] = bc.latest_price

        # RVOL: el Advisor debe ver el mayor entre Fast Path (vela en formación)
        # y Slow Path (vela cerrada) para detectar Absorción Institucional.
        if bc._live_rvol > 0:
            slow_rvol    = (tactical.get("diagnostic") or {}).get("rvol", 0)
            max_rvol     = max(float(slow_rvol), bc._live_rvol)
            diag_copy    = dict(tactical.get("diagnostic") or {})
            diag_copy["rvol"] = round(max_rvol, 2)
            live_overrides["diagnostic"] = diag_copy

        if live_overrides:
            tactical = {**tactical, **live_overrides}

        # ── 2. MTF: Guardar snapshot + lógica Capitán ─────────────────────────
        sanitized_current = sanitize_for_json(tactical)
        await bc._store.save_tactical_snapshot(self._symbol, self._interval, sanitized_current)

        IS_LEAD = (self._interval == "15m")
        if not IS_LEAD:
            existing = await bc._store.get_advisor_advice(self._symbol)
            if existing:
                self._last_advisor_obj = existing
                await bc._broadcast({"type": "advisor_update", "data": existing})
                return
            if not is_absorption_alert:
                return  # Esperamos al 15m

        # ── 3. Caché de candle (evita re-llamar a Ollama en la misma vela) ────
        current_candle_ts = (
            tactical.get("candles", [{}])[-1].get("timestamp", 0)
            if tactical.get("candles") else 0
        )
        existing = await bc._store.get_advisor_advice(self._symbol)
        if existing and existing.get("timestamp") == current_candle_ts:
            content = existing.get("content", "")
            if "N/A" not in content and "ESTRUCTURA NO IDENTIFICADA" not in content:
                logger.debug(f"[ADVISOR_BRIDGE] ♻️ Cache hit para {self._symbol} ({current_candle_ts})")
                self._last_advisor_obj = existing
                await bc._broadcast({"type": "advisor_update", "data": existing})
                return
            else:
                logger.info(f"[ADVISOR_BRIDGE] 🔃 Re-generando análisis para {self._symbol} (caché inválido)")

        # ── 4. Check Ollama (fail-fast) ───────────────────────────────────────
        if not await check_ollama_status():
            logger.info(f"[ADVISOR_BRIDGE] ⚠️ Ollama offline para {self._symbol}")
            await bc._broadcast({"type": "advisor_update", "data": {
                "asset":      self._symbol,
                "content": (
                    "⚠️ MOTOR IA OFFLINE: El motor Ollama no responde en localhost:11434. "
                    "Asegúrate de que Ollama esté abierto."
                ),
                "timestamp":  current_candle_ts,
                "status":     "OFFLINE",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }})
            return

        # ── 5. Caché semántica MD5 ────────────────────────────────────────────
        tactical_hash = self.get_tactical_hash(tactical)
        cache_hit     = self._last_tactical_hash == tactical_hash

        if cache_hit and not is_absorption_alert:
            logger.info(f"[ADVISOR_BRIDGE] 🧠 Cache semántico HIT para {self._symbol}. Contexto idéntico.")
            if self._last_advisor_obj:
                await bc._broadcast({"type": "advisor_update", "data": self._last_advisor_obj})
                return

        self._last_tactical_hash = tactical_hash

        # ── 6. Etiqueta de Absorción Institucional ────────────────────────────
        if is_absorption_alert:
            logger.info(f"[ADVISOR_BRIDGE] 🧪 Inyectando etiqueta ABSORCIÓN para {self._symbol}...")
            tactical["alert_type"] = "ALERTA DE ABSORCIÓN"
            tactical["priority"]   = "MAXIMA"

        logger.info(f"[ADVISOR_BRIDGE] 🧠 Iniciando análisis LLM para {self._symbol}...")

        # ── 7. Cancelar tarea previa que aún esté corriendo ──────────────────
        if self._advisor_task and not self._advisor_task.done():
            self._advisor_task.cancel()
            logger.info(f"[ADVISOR_BRIDGE] 🔃 Análisis previo cancelado para {self._symbol} (nueva petición)")

        try:
            # ── 8. Gatekeeping Cognitivo (bypass Ollama si mercado neutral) ──
            approved_signals = tactical.get("signals", [])
            blocked_signals  = tactical.get("blocked_signals", [])
            all_signals      = approved_signals + blocked_signals

            conf_score = max(
                (s.get("confluence", {}).get("score", 0) for s in all_signals if s.get("confluence")),
                default=0
            )
            conf_score = max(conf_score, tactical.get("confluence_score", 0))

            is_active_signal = any(
                s.get("signal_type", s.get("type", "NEUTRAL")) != "NEUTRAL"
                for s in approved_signals
            ) if approved_signals else False

            regime     = tactical.get("market_regime", "UNKNOWN")
            is_trending = regime in ("MARKUP", "MARKDOWN", "ACCUMULATION", "DISTRIBUTION")

            logger.info(
                f"[ADVISOR_BRIDGE] {self._symbol} | Score: {conf_score}% | "
                f"Active: {is_active_signal} | Regime: {regime} | "
                f"Signals: {len(approved_signals)}A/{len(blocked_signals)}B"
            )

            if not is_active_signal and not is_trending and conf_score < 40:
                # Bypass total — mercado en standby
                advice_json = {
                    "verdict": "SIDEWAYS",
                    "logic":   f"CONFLUENCIA BAJA ({conf_score}%). AGUARDANDO VOLATILIDAD... 🛡️",
                    "threat":  "LOW",
                }
                advice = json.dumps(advice_json)
                logger.info(f"[ADVISOR_BRIDGE] 🛡️ Gatekeeping ACTIVE para {self._symbol}. Motivo: Confluencia {conf_score}% (Standby)")
                
                # Broadcast inmediato del bypass para limpiar loading en UI
                await bc._broadcast({"type": "advisor_update", "data": {
                    "content":    advice_json["logic"],
                    "symbol":     self._symbol,
                    "status":     "GATEKEEPING",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }})
            else:
                # ── 9. Loading indicator ──────────────────────────────────────
                await bc._broadcast({"type": "advisor_update", "data": {
                    "asset":      self._symbol,
                    "content":    "CONECTANDO CON EL MOTOR CUÁNTICO (Ollama)... ⚡",
                    "timestamp":  current_candle_ts,
                    "status":     "LOADING_IA",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }})
                self._advisor_task = asyncio.current_task()

                # ── 10. Llamada al LLM ───────────────────────────────────────
                news_items   = await bc._store.get_news(limit=5)
                liqs         = await bc._store.get_liquidation_clusters(self._symbol)
                econ_events  = await bc._store.get_economic_events(limit=5)

                sanitized = sanitize_for_json(tactical.copy())
                sanitized.pop("candles", None)
                mtf_context = await bc._store.get_mtf_context(self._symbol)

                # Prioridad 0 para el símbolo activo del usuario
                advice = await asyncio.wait_for(
                    generate_tactical_advice(
                        self._symbol,
                        tactical_data    = sanitized,
                        current_session  = session_state.get("data", {}).get("current_session", "UNKNOWN"),
                        ml_projection    = bc._last_ml,
                        news             = news_items,
                        liquidations     = liqs,
                        economic_events  = econ_events,
                        onchain_data     = bc._last_onchain.get("data") if bc._last_onchain else None,
                        mtf_context      = mtf_context,
                    ),
                    timeout=90.0,
                )
                logger.info(f"[ADVISOR_BRIDGE] ✅ Análisis LLM completado para {self._symbol}")

            # ── 11. Guardar y broadcast ──────────────────────────────────────
            advice_obj = {
                "timestamp":  current_candle_ts,
                "asset":      self._symbol,
                "content":    advice,
                "status":     "COMPLETE",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            await bc._store.save_advisor_advice(self._symbol, advice_obj)
            self._last_advisor_obj = advice_obj
            await bc._broadcast({"type": "advisor_update", "data": advice_obj})

        except asyncio.TimeoutError:
            logger.info(f"[ADVISOR_BRIDGE] ⚠️ Timeout en LLM Advisor ({self._symbol})")
            error_obj = {
                "asset":   self._symbol,
                "content": (
                    "⚠️ MOTOR IA SATURADO: Ollama está tardando demasiado. "
                    "Reintentando en la próxima vela..."
                ),
                "timestamp":  current_candle_ts,
                "status":     "TIMEOUT",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            self._last_advisor_obj = error_obj
            await bc._broadcast({"type": "advisor_update", "data": error_obj})

        except asyncio.CancelledError:
            pass  # Cancelación limpia — no es un error

        except Exception as e:
            import traceback
            logger.error(f"[ADVISOR_BRIDGE] ❌ {self._symbol}:{self._interval} → Advisor error: {e}")
            await bc._broadcast({"type": "advisor_update", "data": {
                "asset":      self._symbol,
                "content":    f"ADVISOR OFFLINE: {e}",
                "status":     "ERROR",
                "timestamp":  current_candle_ts,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }})
            traceback.print_exc()
