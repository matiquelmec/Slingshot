"""
=============================================================================
SLINGSHOT TELEGRAM INSTITUTIONAL DISPATCHER v17.0
=============================================================================
Enruta señales institucionales aprobadas directamente a la app móvil de Telegram
con formato formateado para copiar en 1 toque en MetaTrader 5 (MT5 / cTrader).
"""
import asyncio
import httpx
import time
import json
from pathlib import Path
from typing import Dict, Any, Optional
from engine.core.logger import logger
from engine.api.config import settings

_STATE_FILE = Path(__file__).parent.parent / "data" / "telegram_sent_state.json"

class TelegramDispatcher:
    """Despachador asíncrono de alertas de alta velocidad para Telegram con deduplicación inteligente y persistencia en SQLite WAL."""

    def __init__(self, cooldown_seconds: int = 1800):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        raw_chat_id = settings.TELEGRAM_CHAT_ID or ""
        # Soporta múltiples chat IDs separados por comas (ej: "6463158372, -5422257440")
        self.chat_ids = [cid.strip() for cid in raw_chat_id.split(",") if cid.strip()]
        self.enabled = settings.ENABLE_TELEGRAM_ALERTS and bool(self.bot_token and self.chat_ids)
        self.cooldown_seconds = cooldown_seconds
        self._lock = asyncio.Lock()
        self._last_dispatch_time = 0.0
        from engine.core.vault import vault
        self._vault = vault
        self._sent_state: Dict[str, float] = self._load_sent_state()

    # ── SOP-120: Anti-Spam Gate persistente (sobrevive reinicios del VPS) ──
    def _load_sent_state(self) -> Dict[str, float]:
        try:
            if _STATE_FILE.exists():
                data = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return {k: float(v) for k, v in data.items() if isinstance(v, (int, float))}
        except Exception:
            pass
        return {}

    def _persist_sent_state(self) -> None:
        try:
            _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            _STATE_FILE.write_text(json.dumps(self._sent_state), encoding="utf-8")
        except Exception as e:
            logger.debug(f"[TELEGRAM] No se pudo persistir estado anti-spam: {e}")

    def _should_dispatch(self, key: str, ttl_seconds: int) -> bool:
        """Devuelve True solo si el evento `key` no se envió dentro de `ttl_seconds`."""
        now = time.time()
        # Purga de entradas expiradas (máx. 48h) para que el archivo no crezca sin límite
        self._sent_state = {k: t for k, t in self._sent_state.items() if now - t < 172800}
        last = self._sent_state.get(key)
        if last is not None and (now - last) < ttl_seconds:
            logger.debug(f"[TELEGRAM] Suprimido duplicado '{key}' ({int(now - last)}s < {ttl_seconds}s)")
            return False
        self._sent_state[key] = now
        self._persist_sent_state()
        return True

    @staticmethod
    def _validate_signal_sanity(
        asset: str,
        direction: str,
        price: float,
        stop_loss: float,
        timeframe: str,
        current_price: Optional[float],
        is_fresh_execution: bool,
        is_test: bool,
    ) -> tuple[bool, str]:
        """
        SOP-132 Hard Sanity Gate:
        Garantiza coherencia geométrica, distancia de SL realista y cercanía al precio spot.
        """
        if price <= 0 or stop_loss <= 0 or price == stop_loss:
            return False, "Precio o Stop Loss inválido (<= 0 o iguales)"

        is_long = "LONG" in direction
        if is_long and stop_loss >= price:
            return False, f"Geometría inválida LONG: SL ({stop_loss}) >= Entrada ({price})"
        if not is_long and stop_loss <= price:
            return False, f"Geometría inválida SHORT: SL ({stop_loss}) <= Entrada ({price})"

        # Bloquear referencias estructurales 1D no ejecutadas (ruido desconectado del spot)
        if not is_test and not is_fresh_execution and str(timeframe).lower() == "1d":
            return False, "Señal 1D estructural no ejecutada bloqueada (SOP-132)"

        # Validar distancia porcentual de Stop Loss
        sl_pct = abs(price - stop_loss) / price
        is_tradfi = any(k in asset.upper() for k in ("XAU", "XAG", "US30", "US100", "SPX500", "NAS100", "DJI", "EURUSD", "GBPUSD", "USDJPY"))
        min_sl_pct = 0.0005 if is_tradfi else 0.0025
        max_sl_pct = 0.035
        if sl_pct < min_sl_pct or sl_pct > max_sl_pct:
            return False, f"Distancia SL fuera de rango ({sl_pct*100:.2f}%, permitido {min_sl_pct*100:.2f}%-{max_sl_pct*100:.2f}%)"

        # Validar coherencia contra precio spot actual si está disponible
        if current_price is not None and current_price > 0 and not is_fresh_execution:
            max_drift = 0.012 if str(timeframe).lower() in ("1m", "3m", "5m", "15m") else 0.015
            drift = abs(price - current_price) / current_price
            if drift > max_drift:
                return False, f"Drift excesivo vs Spot ({drift*100:.2f}% > {max_drift*100:.2f}%)"
            if is_long and price > current_price * 1.0015:
                return False, f"Orden BUY LIMIT por encima del Spot ({price} > {current_price})"
            if not is_long and price < current_price * 0.9985:
                return False, f"Orden SELL LIMIT por debajo del Spot ({price} < {current_price})"

        return True, "OK"

    @staticmethod
    def _resolve_tp_levels(
        signal: Dict[str, Any],
        price: float,
        dist: float,
        is_long: bool,
    ) -> tuple[float, float, float]:
        """
        Respeta los TP reales de la señal/orden Bitunix (SOP-132).
        Solo usa la grilla auditada 1.2R / 2.0R / 3.0R si faltan o son inválidos.
        """
        sign = 1.0 if is_long else -1.0
        raw_tp1 = float(signal.get("tp1") or 0.0)
        raw_tp2 = float(signal.get("tp2") or 0.0)
        raw_tp3 = float(signal.get("tp3") or signal.get("take_profit_3r") or 0.0)

        def _valid_tp(val: float) -> bool:
            if val <= 0:
                return False
            return (val > price) if is_long else (val < price)

        if _valid_tp(raw_tp1) and _valid_tp(raw_tp2) and _valid_tp(raw_tp3):
            ordered = (raw_tp1 < raw_tp2 <= raw_tp3) if is_long else (raw_tp1 > raw_tp2 >= raw_tp3)
            if ordered:
                return raw_tp1, raw_tp2, raw_tp3

        return (
            price + (dist * 1.2 * sign),
            price + (dist * 2.0 * sign),
            price + (dist * 3.0 * sign),
        )

    async def send_signal_alert(self, signal: Dict[str, Any], account_profile: str = "FTMO_100K") -> bool:
        """
        Envía una alerta institucional minimalista y privada a Telegram (SOP-132).
        - Valida coherencia geométrica, distancia SL y cercanía al precio spot.
        - Respeta los niveles TP reales sin sobrescritura ficticia.
        - Oculta por completo balances, montos en USD, lotajes y nombres de cuenta.
        """
        if not self.enabled:
            logger.debug("[TELEGRAM] 🔕 Alertas de Telegram desactivadas o credenciales no configuradas.")
            return False

        asset = signal.get('asset', signal.get('symbol', 'UNKNOWN'))
        direction = signal.get('signal_type', signal.get('type', signal.get('direction', 'LONG'))).upper()
        price = float(signal.get('price', 0.0))
        stop_loss = float(signal.get('stop_loss', 0.0))
        score = int(signal.get('confluence_score', signal.get('score', 0)))
        timeframe = signal.get('timeframe', signal.get('interval', '15m'))
        is_test = bool(signal.get('is_test', False))

        raw_spot = signal.get('current_price', signal.get('spot_price'))
        current_price = float(raw_spot) if raw_spot is not None and float(raw_spot) > 0 else None

        # ── 1. DEDUPLICACIÓN DE CICLO DE VIDA ──
        dedup_key = f"{asset}_{direction}_{timeframe}"
        exec_status = signal.get("execution_status")
        is_fresh_execution = isinstance(exec_status, dict) and bool(exec_status.get("placed"))

        if not is_test:
            if not is_fresh_execution:
                try:
                    from engine.execution.nexus import nexus
                    active_syms = {p.get("signal", {}).get("asset", "").upper() for p in nexus._active_positions.values()}
                    pending_limits = {s.upper() for s in getattr(nexus, "_pending_limit_symbols", set())}
                    if asset.upper() in active_syms or asset.upper() in pending_limits:
                        logger.debug(f"[TELEGRAM] 🛡️ Alerta {asset} {direction} suprimida: trade activo/pendiente.")
                        return False
                except Exception as nexus_chk_err:
                    logger.debug(f"[TELEGRAM] Fallback comprobación Nexus: {nexus_chk_err}")

            is_blocked, elapsed, pct_diff = self._vault.is_signal_in_cooldown(
                dedup_key=dedup_key,
                current_price=price,
                cooldown_seconds=14400,
                max_drift_pct=2.5
            )
            if is_blocked:
                logger.debug(f"[TELEGRAM] ⏳ Alerta {asset} {direction} ({timeframe}) bloqueada por cooldown ({elapsed}s / diff {pct_diff:.2f}%)")
                return False

        # ── 2. FILTRO DE CONFLUENCIA Y HARD SANITY GATE (SOP-132) ──
        if score < 60:
            logger.debug(f"[TELEGRAM] Señal {asset} {direction} ignorada (Score {score}% < 60%)")
            return False

        sane, sanity_reason = self._validate_signal_sanity(
            asset=asset,
            direction=direction,
            price=price,
            stop_loss=stop_loss,
            timeframe=timeframe,
            current_price=current_price,
            is_fresh_execution=is_fresh_execution,
            is_test=is_test,
        )
        if not sane:
            logger.warning(f"[TELEGRAM] 🛡️ Señal {asset} {direction} rechazada por Sanity Gate: {sanity_reason}")
            return False

        # Veto institucional: Índices de EE.UU. no deben operar en sesión ASIA
        from engine.core.session_manager import classify_market_session
        live_session_info = classify_market_session()
        computed_session = live_session_info.get("session_label", "OFF_HOURS")
        session = signal.get('session')
        if not session or session in ("UNKNOWN", "KILLZONE", "NEW_YORK", "LIVE_SIGNAL"):
            session = computed_session
        elif session in live_session_info:
            session = live_session_info["session_label"]

        is_us_index = any(idx in asset.upper() for idx in ("US30", "US100", "SPX500", "NAS100", "DJI"))
        if is_us_index and "ASIA" in session:
            logger.warning(f"[TELEGRAM] 🛡️ Veto de Sesión: {asset} bloqueado en {session}.")
            return False

        # ── 3. NIVELES TÉCNICOS REALES (SIN DATOS DE CUENTA NI USD) ──
        is_long = "LONG" in direction
        dist = abs(price - stop_loss)
        tp1, tp2, tp3 = self._resolve_tp_levels(signal, price, dist, is_long)

        r1 = abs(tp1 - price) / dist
        r2 = abs(tp2 - price) / dist
        r3 = abs(tp3 - price) / dist
        sl_pct = (dist / price) * 100.0

        decimals = 4 if price < 10.0 else 2
        sym_display = asset.replace("USDT", "USD") if is_us_index else asset
        dir_label = "LONG" if is_long else "SHORT"
        dir_icon = "🟢" if is_long else "🔴"

        p_str = f"{price:.{decimals}f}"
        sl_str = f"{stop_loss:.{decimals}f}"
        tp1_str = f"{tp1:.{decimals}f}"
        tp2_str = f"{tp2:.{decimals}f}"
        tp3_str = f"{tp3:.{decimals}f}"
        spot_suffix = f" (Spot: <code>{current_price:.{decimals}f}</code>)" if current_price else ""

        if is_fresh_execution:
            oid_str = str(exec_status.get("order_id") or "")[:12]
            oid_tag = f" (#{oid_str})" if oid_str else ""
            status_line = f"⚡ <b>ORDEN LÍMITE ACTIVA EN BITUNIX</b>{oid_tag}"
        else:
            status_line = f"⏳ <b>SEÑAL INSTITUCIONAL</b> • {session.split(' ')[0]}"

        message = (
            f"{dir_icon} <b>{dir_label} {sym_display}</b> (<code>{timeframe}</code>) • Score <b>{score}%</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<b>Entrada:</b> <code>{p_str}</code>{spot_suffix}\n"
            f"<b>Stop Loss:</b> <code>{sl_str}</code> (-{sl_pct:.2f}%)\n"
            f"<b>TP1 (50%):</b> <code>{tp1_str}</code> (+{r1:.1f}R)\n"
            f"<b>TP2 (30%):</b> <code>{tp2_str}</code> (+{r2:.1f}R)\n"
            f"<b>TP3 (20%):</b> <code>{tp3_str}</code> (+{r3:.1f}R)\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"{status_line}"
        )

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        any_success = False

        try:
            # ── 3. THROTTLE SECUENCIAL (500ms entre mensajes para evitar HTTP 429) ──
            async with self._lock:
                elapsed_since_last = time.time() - self._last_dispatch_time
                if elapsed_since_last < 0.5:
                    await asyncio.sleep(0.5 - elapsed_since_last)

                async with httpx.AsyncClient(timeout=5.0) as client:
                    for target_chat_id in self.chat_ids:
                        payload = {
                            "chat_id": target_chat_id,
                            "text": message,
                            "parse_mode": "HTML",
                            "disable_web_page_preview": True
                        }
                        resp = await client.post(url, json=payload)
                        self._last_dispatch_time = time.time()
                        
                        if resp.status_code == 200:
                            logger.info(f"[TELEGRAM] 📲 Alerta enviada con éxito a {target_chat_id} para {sym_display} {direction}")
                            any_success = True
                        else:
                            # Sanitizar URL para no exponer bot token en logs
                            logger.error(f"[TELEGRAM] ❌ Error enviando a {target_chat_id}: {resp.status_code} - {resp.text}")

                    if any_success:
                        if not is_test:
                            self._vault.record_signal_dispatch(
                                dedup_key=dedup_key,
                                asset=asset,
                                direction=direction,
                                timeframe=timeframe,
                                price=price
                            )
                        return True
                    return False
        except Exception as e:
            logger.error(f"[TELEGRAM] ❌ Excepción en Telegram Dispatcher: {e}")
            return False

    async def send_heartbeat_report(self, stats: Dict[str, Any]) -> bool:
        """Despacha reporte de signos vitales (Heartbeat) sin exponer balances ni PnL en USD."""
        if not self.enabled:
            return False
        uptime = stats.get("uptime_hours", 0.0)
        lat = stats.get("latency_ms", 0.0)
        positions = stats.get("positions", [])
        
        pos_lines = []
        for p in positions:
            pos_lines.append(f"   • <b>{p.get('symbol')}</b> ({p.get('side')}) | SL: {p.get('sl')}")
        pos_text = "\n".join(pos_lines) if pos_lines else "   • <i>Sin posiciones abiertas actualmente.</i>"
        
        msg = (
            f"💓 <b>SLINGSHOT — PULSO OPERACIONAL</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"⏱️ <b>Uptime:</b> <code>{uptime:.1f}h</code> | ⚡ <b>Latencia:</b> <code>{lat:.1f}ms</code>\n"
            f"📊 <b>POSICIONES ACTIVAS:</b>\n"
            f"{pos_text}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🟢 <i>Centinelas y salvaguardas activos.</i>"
        )
        return await self.send_raw_message(msg)

    async def send_system_alert(self, title: str, details: str, severity: str = "WARNING", cooldown_seconds: int = 300) -> bool:
        """Despacha alertas críticas de sistema (SOP-25, mitigaciones, errores de red)."""
        if not self.enabled:
            return False
        if not self._should_dispatch(f"sys:{title}", cooldown_seconds):
            return False
        icon = "🚨" if severity.upper() == "CRITICAL" else ("⚠️" if severity.upper() == "WARNING" else "ℹ️")
        msg = (
            f"{icon} <b>ALERTA DE SISTEMA: {title}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Severidad:</b> <code>{severity.upper()}</code>\n"
            f"<b>Detalles:</b>\n{details}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )
        return await self.send_raw_message(msg)
    async def send_raw_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Envía un mensaje de texto directo a todos los destinatarios configurados."""
        if not self.enabled:
            return False
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        any_success = False
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                for cid in self.chat_ids:
                    payload = {"chat_id": cid, "text": text, "parse_mode": parse_mode}
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        any_success = True
                    else:
                        payload.pop("parse_mode", None)
                        retry_resp = await client.post(url, json=payload)
                        if retry_resp.status_code == 200:
                            any_success = True
            return any_success
        except Exception as e:
            logger.debug(f"[TELEGRAM] Error en send_raw_message: {e}")
            return False




    async def send_trade_fill_alert(self, symbol: str, side: str, price: float, qty: float = 0.0, account_label: str = "Primary") -> bool:
        if not self.enabled:
            return False
        if not self._should_dispatch(f"fill:{account_label}:{symbol}:{side.upper()}:{price:.6g}", 86400):
            return False
        sym = symbol.replace("USDT", "USD")
        side_icon = "LONG" if "BUY" in side.upper() or "LONG" in side.upper() else "SHORT"
        text = f"⚡ ORDEN EJECUTADA ({side_icon}): {sym} @ {price:.4f}"
        return await self.send_raw_message(text)

    async def send_tp_hit_alert(self, symbol: str, tp_label: str, exit_price: float, pnl_usd: float = 0.0, is_be: bool = True, pnl_r: Optional[float] = None) -> bool:
        if not self.enabled:
            return False
        if not self._should_dispatch(f"tp:{symbol}:{tp_label.upper()}", 43200):
            return False
        sym = symbol.replace("USDT", "USD")
        be_str = " | SL a BREAKEVEN" if is_be else ""
        r_str = f" ({pnl_r:+.2f}R)" if pnl_r is not None else ""
        text = f"🎯 HIT TP: {tp_label.upper()} en {sym} @ {exit_price:.4f}{r_str}{be_str}"
        return await self.send_raw_message(text)

    async def send_trade_closed_alert(self, symbol: str, reason: str, exit_price: float, pnl_usd: float = 0.0, pnl_r: float = 0.0) -> bool:
        if not self.enabled:
            return False
        if not self._should_dispatch(f"closed:{symbol}:{exit_price:.6g}", 86400):
            return False
        sym = symbol.replace("USDT", "USD")
        text = f"🏁 TRADE CERRADO: {sym} ({reason}) @ {exit_price:.4f} | Resultado: {pnl_r:+.2f}R"
        return await self.send_raw_message(text)

    async def send_unauthorized_position_alert(self, symbol: str, side: str, qty: float = 0.0, account_label: str = "Primary") -> bool:
        if not self.enabled:
            return False
        # Una sola alerta por posición (re-aviso cada 12h si sigue abierta), no cada ciclo de 15s
        if not self._should_dispatch(f"unauth:{account_label}:{symbol}:{side.upper()}", 43200):
            return False
        text = (
            f"🚨 <b>[ALERTA DE SEGURIDAD SLINGSHOT]</b>\n"
            f"<b>Posición Externa No Canónica Detectada</b>\n"
            f"• <b>Activo:</b> <code>{symbol}</code> ({side})\n"
            f"⚠️ Rechazada su adopción en Nexus (fuera del universo canónico). Gestione manualmente."
        )
        return await self.send_raw_message(text, parse_mode="HTML")

# Instancia singleton para importacion
telegram_dispatcher = TelegramDispatcher()

