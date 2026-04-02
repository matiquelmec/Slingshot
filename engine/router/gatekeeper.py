"""
engine/router/gatekeeper.py — Slingshot v4.1 Platinum
=======================================================
El Portero Institucional — 3 capas de filtrado en secuencia.

FILTRO 1 — Direccional HTF:   ¿La señal sigue el sesgo institucional H1/H4?
FILTRO 2 — Ratio R:R:          ¿La geometría matemática cumple R:R ≥ 1.8?
FILTRO 3 — Score de Confluencia: ¿El Jurado Neural otorga ≥ 75% de confianza?
FILTRO 4 — Path Traversal:     ¿La señal sigue viva (no expiró, no tocó SL/TP)?

Una señal rechazada en cualquier filtro NO se descarta:
se archiva en 'blocked_signals' para el Modo Auditoría del Frontend.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from engine.core.confluence import confluence_manager
from engine.risk.risk_manager import RiskManager


@dataclass
class GatekeeperContext:
    """
    Contexto externo para el Jurado de Confluencia.
    Todos los campos son opcionales para robustez ante datos faltantes.
    """
    ml_projection: dict = field(default_factory=dict)
    session_data: dict = field(default_factory=dict)
    news_items: list = field(default_factory=list)
    economic_events: list = field(default_factory=list)
    liquidation_clusters: list = field(default_factory=list)


@dataclass
class GatekeeperResult:
    """Resultado del proceso de filtrado para un lote de señales."""
    approved: list[dict] = field(default_factory=list)
    blocked: list[dict] = field(default_factory=list)


class SignalGatekeeper:
    """
    Aplica los 4 filtros institucionales en secuencia.
    Separa señales aprobadas de las bloqueadas (modo auditoría).
    """

    def __init__(self, risk_manager: RiskManager):
        self._risk = risk_manager

    def process(
        self,
        signals: list[dict],
        df: pd.DataFrame,
        smc_map: dict,
        key_levels: list,
        interval: str,
        htf_bias=None,
        context: GatekeeperContext | None = None,
        silent: bool = False,
    ) -> GatekeeperResult:
        """
        Procesa un lote de señales aplicando los 4 porteros en cadena.
        """
        if context is None:
            context = GatekeeperContext()

        result = GatekeeperResult()

        # Pre-calcular vectores de tiempo para Path Traversal (performance)
        try:
            df_time  = pd.to_datetime(df["timestamp"], utc=True)
            df_low   = df["low"].values
            df_high  = df["high"].values
            now_utc  = df_time.iloc[-1]
        except Exception:
            df_time = df_low = df_high = now_utc = None

        for sig in signals[-10:]:  # Ventana de las últimas 10 señales
            # ── Filtro 1: Enriquecimiento de Riesgo ──────────────────────────
            risk_data = self._risk.calculate_position(
                current_price=sig["price"],
                signal_type=sig.get("signal_type", "LONG"),
                market_regime=sig.get("regime", "RANGING"),
                key_levels=key_levels,
                smc_data=smc_map,
                atr_value=sig.get("atr_value", 0.0),
            )
            # (El enriquecimiento real lo hace el dispatcher; aquí validamos)

            # ── Filtro 2: Direccional HTF ─────────────────────────────────────
            if htf_bias and htf_bias.direction != "NEUTRAL":
                is_long = "LONG" in str(sig.get("type", "")).upper()
                if htf_bias.direction == "BULLISH" and not is_long:
                    self._block(sig, "BLOCKED_BY_HTF", f"Contra sesgo HTF Alcista: {htf_bias.reason}", result)
                    continue
                if htf_bias.direction == "BEARISH" and is_long:
                    self._block(sig, "BLOCKED_BY_HTF", f"Contra sesgo HTF Bajista: {htf_bias.reason}", result)
                    continue

            # ── Filtro 3: Jurado de Confluencia ───────────────────────────────
            try:
                confluence_result = confluence_manager.evaluate_signal(
                    df=df,
                    signal=sig,
                    ml_projection=context.ml_projection,
                    session_data=context.session_data,
                    news_items=context.news_items,
                    economic_events=context.economic_events,
                    liquidation_clusters=context.liquidation_clusters,
                )
                sig["confluence"] = confluence_result
            except Exception as e:
                print(f"[GATEKEEPER] ConfluenceManager error: {e}")
                sig["confluence"] = None

            # ── Filtro 4: R:R Mínimo ──────────────────────────────────────────
            rr = self._risk.validate_signal(sig)
            sig["rr_ratio"]     = rr["rr_ratio"]
            sig["trade_quality"] = rr["trade_quality"]

            if not rr["approved"]:
                if not silent:
                    print(f"[GATEKEEPER] 🔴 R:R insuficiente | {sig.get('signal_type')} | {rr['reason']}")
                self._block(sig, "BLOCKED_BY_FILTER", rr["reason"], result)
                continue

            # ── Filtro 5: Score de Confluencia ≥ 75% ─────────────────────────
            score = sig["confluence"].get("score", 0) if sig.get("confluence") else 0
            if score < 75:
                if not silent:
                    print(f"[GATEKEEPER] 🔴 Confluencia {score}% < 75% — señal bloqueada")
                self._block(sig, "BLOCKED_BY_CONFIDENCE", f"Confianza {score}% < 75%", result)
                continue

            # ── Filtro 6: Path Traversal — ¿Sigue Viva? ──────────────────────
            if not self._is_alive(sig, df_time, df_low, df_high, now_utc):
                self._block(sig, "BLOCKED_EXPIRED", "Señal expirada o tocó SL/TP", result)
                continue

            result.approved.append(sig)

        return result

    # ── Helpers privados ─────────────────────────────────────────────────────

    @staticmethod
    def _block(sig: dict, status: str, reason: str, result: GatekeeperResult):
        sig["status"] = status
        sig["blocked_reason"] = reason
        result.blocked.append(sig)

    @staticmethod
    def _is_alive(sig: dict, df_time, df_low, df_high, now_utc) -> bool:
        """Path Traversal vectorizado: verifica si la señal sigue activa."""
        if now_utc is None:
            return True

        expiry_str = sig.get("expiry_timestamp")
        if expiry_str:
            try:
                if now_utc > pd.to_datetime(expiry_str, utc=True):
                    return False
            except Exception:
                pass

        sl = float(sig.get("stop_loss", 0))
        tp = float(sig.get("take_profit_3r", 0))
        if sl <= 0 or tp <= 0:
            return True

        try:
            sig_time = pd.to_datetime(sig.get("timestamp"), utc=True)
            mask     = df_time >= sig_time
            if not mask.any():
                return True

            lows  = df_low[mask]
            highs = df_high[mask]
            is_long = "LONG" in str(sig.get("type", "")).upper()

            if is_long:
                return not ((lows <= sl).any() or (highs >= tp).any())
            else:
                return not ((highs >= sl).any() or (lows <= tp).any())
        except Exception:
            return True
