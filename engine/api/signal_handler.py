"""
engine/api/signal_handler.py — v6.0.1 (Extraído de ws_manager.py)
=========================================================
Responsabilidad: Filtrado institucional, persistencia y notificación de señales.

Extraído del SymbolBroadcaster como parte del refactor ISS-011.
Antes vivía en ws_manager.py como métodos privados (_handle_signals, _persist_signal).

Módulos equivalentes ya extraídos:
  registry.py      — BroadcasterRegistry
  json_utils.py    — sanitize_for_json
  signal_handler.py — (ESTE) Filtrado + persistencia de señales
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from engine.api.registry import registry
from engine.core.logger import logger
from engine.core.store import store
from engine.indicators.ghost_data import get_ghost_state, filter_signals_by_macro
from engine.notifications.telegram import send_signal_async
from engine.notifications.filter import signal_filter

if TYPE_CHECKING:
    # Evitar importación circular — solo para type hints
    pass


class SignalHandler:
    """
    Gestiona el ciclo de vida de las señales del SymbolBroadcaster.

    Responsabilidades:
      1. Debounce institucional (anti-spam por candle)
      2. Filtro macro (Ghost Data)
      3. Notificación Telegram (con cooldown)
      4. Persistencia en MemoryStore local
      5. Broadcast al Dashboard (solo señales ACTIVAS de alta calidad)
    """

    def __init__(self, symbol: str, interval: str, broadcaster_ref):
        """
        Args:
            symbol: Ej. "BTCUSDT"
            interval: Ej. "15m"
            broadcaster_ref: Referencia al SymbolBroadcaster padre (para _broadcast y _store).
        """
        self._symbol   = symbol.upper()
        self._interval = interval
        self._bc       = broadcaster_ref  # Referencia al broadcaster padre
        self._processed_signals_this_candle: set = set()

    def reset_candle(self):
        """Limpia el set de señales procesadas al inicio de cada nueva vela."""
        self._processed_signals_this_candle.clear()

    # ── API Pública ───────────────────────────────────────────────────────────

    async def handle(self, tactical: dict, silent: bool = False):
        """
        Punto de entrada principal.
        Filtra, notifica y persiste señales del resultado táctico.
        """
        raw_signals    = tactical.get("signals", [])
        router_blocked = tactical.get("blocked_signals", [])

        if not raw_signals and not router_blocked:
            return

        # ── Debounce Institucional ────────────────────────────────────────────
        # [v8.2.0] Eliminamos min_score=60 porque el Gatekeeper dictamina (ej BTC puede ser 30%)
        unique_new     = self._debounce(raw_signals,    min_score=0)
        unique_blocked = self._debounce(router_blocked, min_score=0)

        if not unique_new and not unique_blocked:
            return  # Todo ya fue procesado en esta vela

        # ── Filtro Macro (Ghost Data) ─────────────────────────────────────────
        ghost                    = get_ghost_state()
        approved, macro_blocked  = filter_signals_by_macro(unique_new, ghost)

        # ── Telegram + Persistencia Activas ───────────────────────────────────
        final_approved = []
        for sig in approved:
            ok_to_send, reason = signal_filter.should_send(self._symbol, sig)
            if ok_to_send:
                asyncio.create_task(send_signal_async(
                    signal=sig, asset=self._symbol,
                    regime=tactical.get("market_regime", "UNKNOWN"),
                    strategy=tactical.get("active_strategy", "N/A")
                ))
                final_approved.append(sig)
            else:
                logger.info(f"[SIGNAL_HANDLER] {self._symbol} → 🔕 Telegram bloqueado: {reason}")
                sig["blocked_reason"] = reason
                macro_blocked.append(sig)

        for sig in final_approved:
            asyncio.create_task(self.persist(sig, tactical, status="ACTIVE", silent=silent))

        # ── Persistencia de Bloqueadas (Audit Mode v8.6.7) ────────────────────
        for sig in macro_blocked:
            motivo = sig.get("blocked_reason", "Bloqueada por filtro macro")
            asyncio.create_task(self.persist(sig, tactical, status="BLOCKED_MACRO", rejection_reason=motivo, silent=silent))
            registry.record_veto(self._symbol, f"MACRO: {motivo}")
            if not silent:
                logger.info(f"[GATEKEEPER] 🔇 Señal macro-bloqueada ({self._symbol}): {motivo}")

        for sig in unique_blocked:
            motivo = sig.get("blocked_reason", "Rechazada por filtro táctico")
            asyncio.create_task(self.persist(sig, tactical, status="BLOCKED_TACTICAL", rejection_reason=motivo, silent=silent))
            registry.record_veto(self._symbol, f"TACTICAL: {motivo}")
            if not silent:
                logger.info(f"[GATEKEEPER] 🔇 Señal router-bloqueada ({self._symbol}): {motivo}")

    async def persist(
        self,
        sig: dict,
        tactical: dict,
        status: str = "ACTIVE",
        rejection_reason: str = None,
        silent: bool = False,
    ):
        """
        Persiste una señal en el MemoryStore local y, si cumple el filtro de calidad,
        la emite al Dashboard vía broadcast.
        """
        ghost = get_ghost_state()

        # ── Timestamp robusto ─────────────────────────────────────────────────
        raw_ts = sig.get("timestamp") or sig.get("time")
        if not raw_ts and "candles" in tactical:
            raw_ts = tactical["candles"][-1]["timestamp"] if tactical["candles"] else None
        final_ts = raw_ts or datetime.now(timezone.utc).isoformat()
        if isinstance(final_ts, (int, float)):
            final_ts = datetime.fromtimestamp(final_ts, tz=timezone.utc).isoformat()

        # ── Cálculo de Riesgo Hipotético (si falta) ──────────────────────────
        risk_pct = sig.get("risk_pct")
        risk_usd = sig.get("risk_amount_usdt", sig.get("risk_usd"))
        pos_size = sig.get("position_size_usdt", sig.get("position_size"))
        lev      = sig.get("leverage", 1)

        if not risk_pct or not pos_size:
            try:
                from engine.risk.risk_manager import RiskManager
                balance = getattr(ghost, "total_balance", 1000.0)
                rm = RiskManager(account_balance=float(balance))
                calc = rm.calculate_position(
                    current_price=float(sig.get("price", 0)),
                    signal_type=sig.get("signal_type", sig.get("type", "LONG")).upper(),
                    market_regime=tactical.get("market_regime", "UNKNOWN"),
                    smc_data=tactical.get("smc"),
                    atr_value=sig.get("atr", 0),
                    asset=self._symbol
                )
                risk_pct = calc.get("risk_pct")
                risk_usd = calc.get("risk_amount_usdt")
                pos_size = calc.get("position_size_usdt")
                lev      = calc.get("leverage")
            except Exception as e:
                logger.error(f"[SIGNAL_HANDLER] Error simulando riesgo: {e}")

        # ── Construcción del Payload ──────────────────────────────────────────
        price      = float(sig.get("price", 0))
        sl         = float(calc.get("stop_loss", sig.get("stop_loss", 0))) if 'calc' in locals() else float(sig.get("stop_loss", 0))
        # Seleccionamos tp3 como el Target 3R primario desde RiskManager v6.7.5
        tp         = float(calc.get("tp3", sig.get("take_profit_3r", 0))) if 'calc' in locals() else float(sig.get("take_profit_3r", 0))
        rr_ratio   = round(abs(tp - price) / abs(price - sl) if abs(price - sl) > 0 else 0, 2)

        # ── Validación de Integridad v8.3.0 ────────────────────────────────────
        if price <= 0:
            logger.error(f"❌ [SIGNAL_HANDLER] Señal con precio INVALIDO (0) para {self._symbol}. Abortando.")
            return

        realtime_data = {
            "asset":            self._symbol,  # [FORCED] Sobrescribir siempre con el símbolo del Broadcaster
            "interval":         self._interval,
            "signal_type":      sig.get("signal_type", sig.get("type", "LONG")).upper(),
            "type":             sig.get("signal_type", sig.get("type", "LONG")).upper(),
            "entry_price":      price,
            "price":            price,
            "stop_loss":        sl,
            "take_profit_3r":   tp,
            "confluence_score": float(sig.get("confluence", {}).get("score", 0)) if sig.get("confluence") else 0,
            "regime":           tactical.get("market_regime", "UNKNOWN"),
            "strategy":         tactical.get("active_strategy", "N/A"),
            "trigger":          sig.get("trigger", "N/A"),
            "status":           status,
            "rejection_reason": rejection_reason,
            "timestamp":        final_ts,
            "confluence":       sig.get("confluence"),
            "risk_pct":         risk_pct,
            "risk_usd":         risk_usd,
            "position_size":    pos_size,
            "leverage":         lev,
            "rr_ratio":         rr_ratio,
            "entry_zone_top":   calc.get("entry_zone_top", sig.get("entry_zone_top")) if 'calc' in locals() else sig.get("entry_zone_top"),
            "entry_zone_bottom": calc.get("entry_zone_bottom", sig.get("entry_zone_bottom")) if 'calc' in locals() else sig.get("entry_zone_bottom"),
            "tp1":              calc.get("tp1", sig.get("tp1")) if 'calc' in locals() else sig.get("tp1"),
            "tp2":              calc.get("tp2", sig.get("tp2")) if 'calc' in locals() else sig.get("tp2"),
            "tp3":              calc.get("tp3", sig.get("tp3")) if 'calc' in locals() else sig.get("tp3"),
        }

        # ── Persistencia en RAM ───────────────────────────────────────────────
        asyncio.create_task(store.save_signal(realtime_data))

        # ── Broadcast Global al Radar (v8.6.5) ────────────────────────────────
        # [COHERENCIA TOTAL] Emitimos todos los estados (PENDING, ACTIVE, FILLED)
        await registry.broadcast_global({"type": "signal_auditor_update", "data": realtime_data})

        icon = "✅" if status == "ACTIVE" else "🚫"
        if not silent:
            logger.info(
                f"[SIGNAL_HANDLER] {icon} Señal ({status}) persistida: "
                f"{realtime_data['signal_type']} {self._symbol} @ ${realtime_data['entry_price']:.2f}"
            )

    # ── Helpers Privados ──────────────────────────────────────────────────────

    def _debounce(self, signals: list, min_score: int = 0) -> list:
        """
        Filtra señales duplicadas dentro del mismo ciclo de vela.
        Genera un ID estable por (symbol, type, timestamp, score).
        """
        unique = []
        for s in signals:
            score = s.get("confluence", {}).get("score", 0) if s.get("confluence") else 0
            if score < min_score:
                continue
            ts  = s.get("timestamp") or s.get("time") or 0
            sid = f"{self._symbol}:{s.get('type', 'LONG')}:{ts}:{score}"
            if sid not in self._processed_signals_this_candle:
                unique.append(s)
                self._processed_signals_this_candle.add(sid)
        return unique
