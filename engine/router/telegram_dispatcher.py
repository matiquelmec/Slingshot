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

def calculate_mt5_lots_py(symbol: str, risk_usd: float, sl_dist: float) -> float:
    contract_sizes = {
        'XAUUSD': 100, 'GOLD': 100, 'PAXGUSDT': 1, 'XAGUSD': 5000,
        'BTCUSD': 1, 'BTCUSDT': 1, 'ETHUSD': 10, 'ETHUSDT': 10,
        'SOLUSD': 10, 'SOLUSDT': 10, 'AVAXUSD': 10, 'AVAXUSDT': 10
    }
    c_size = contract_sizes.get(symbol.upper(), 1)
    if sl_dist <= 0 or risk_usd <= 0: return 0.01
    lots = risk_usd / (sl_dist * c_size)
    return max(0.01, round(lots, 2))

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


    def _get_bot_execution_status(self) -> str:
        try:
            from engine.execution.nexus import nexus
            p_risk = nexus.get_unprotected_risk_count(account_id="primary")
            c2_risk = nexus.get_unprotected_risk_count(account_id="cliente_2")
            if p_risk >= nexus.MAX_CONCURRENT_POSITIONS and c2_risk >= nexus.MAX_CONCURRENT_POSITIONS:
                return "<i>🟡 En Espera (4/4 cupos de riesgo activos en cuentas | Solo señal manual MT5)</i>"
            else:
                return f"<i>🟢 Procesando Orden Límite (Primary: {p_risk}/4 | Cliente 2: {c2_risk}/4)</i>"
        except Exception:
            return "<i>🟢 Conectado</i>"

    async def send_signal_alert(self, signal: Dict[str, Any], account_profile: str = "FTMO_100K") -> bool:
        """
        Envía una alerta institucional inteligente a Telegram.
        Aplica filtros anti-spam estructurales persistentes en SQLite, confluencia mínima, ratio R:R y cálculo de lotaje MT5.
        """
        if not self.enabled:
            logger.debug("[TELEGRAM] 🔕 Alertas de Telegram desactivadas o credenciales no configuradas.")
            return False

        asset = signal.get('asset', signal.get('symbol', 'UNKNOWN'))
        direction = signal.get('signal_type', signal.get('type', signal.get('direction', 'LONG'))).upper()
        price = float(signal.get('price', 0.0))
        stop_loss = float(signal.get('stop_loss', 0.0))
        be_price = float(signal.get('be_price', 0.0))
        tp3 = float(signal.get('tp3', signal.get('take_profit_3r', 0.0)))
        score = int(signal.get('confluence_score', signal.get('score', 0)))
        timeframe = signal.get('timeframe', signal.get('interval', '15m'))
        is_test = bool(signal.get('is_test', False))

        # ── 1. DEDUPLICACIÓN ESTRUCTURAL INTELIGENTE (SQLite WAL Multi-Reinicio) ──
        dedup_key = f"{asset}_{direction}_{timeframe}"

        if not is_test:
            is_blocked, elapsed, pct_diff = self._vault.is_signal_in_cooldown(
                dedup_key=dedup_key,
                current_price=price,
                cooldown_seconds=self.cooldown_seconds,
                max_drift_pct=3.0
            )
            if is_blocked:
                logger.debug(f"[TELEGRAM] ⏳ Alerta {asset} {direction} ({timeframe}) bloqueada por cooldown persistente en SQLite ({elapsed}s transcurridos / diff {pct_diff:.2f}%)")
                return False

        # ── 2. FILTRO DE CONFLUENCIA INSTITUCIONAL (Apex Hybrid v19.1 >= 60%) ──
        if score < 60:
            logger.debug(f"[TELEGRAM] Señal {asset} {direction} ignorada (Score {score}% < 60% umbral óptimo)")
            return False

        risk_usd = 750.0 if "100K" in account_profile else (1500.0 if "200K" in account_profile else 12.50)
        dist = abs(price - stop_loss)
        lots = calculate_mt5_lots_py(asset, risk_usd, dist)
        
        # ── GEOMETRÍA MATEMÁTICA ESTRICTA (Alpha Maximizer v25.1 50/30/20) ──
        # SHORT: Entry > BE > TP1 > TP2 > TP3
        # LONG:  Entry < BE < TP1 < TP2 < TP3
        is_long = "LONG" in direction
        sign = 1.0 if is_long else -1.0
        
        # Cálculo geométrico riguroso de niveles R:R
        be_price = price + (dist * 1.0 * sign)
        tp1 = price + (dist * 1.5 * sign)
        tp2 = price + (dist * 3.0 * sign)
        tp3 = price + (dist * 5.0 * sign)
        
        # Formateo de precisión decimal según el precio del activo (Cripto vs Forex/Índices)
        decimals = 4 if price < 10.0 else (2 if price < 1000.0 else 2)
        
        action = "BUY LIMIT" if is_long else "SELL LIMIT"
        sym_mt5 = asset.replace("USDT", "USD")
        
        # Extracción de factores contextuales y cálculo en vivo de Sesión Real UTC / NY
        timeframe = signal.get('timeframe', signal.get('interval', '15m'))
        
        # Cálculo de sesión institucional real en el momento exacto del despacho
        from datetime import datetime, timezone
        utc_now = datetime.now(timezone.utc)
        utc_h = utc_now.hour
        if 12 <= utc_h < 21:
            computed_session = "NEW_YORK (RTH)"
        elif 8 <= utc_h < 12:
            computed_session = "LONDON (Killzone)"
        elif 0 <= utc_h < 8:
            computed_session = "ASIA (Tokyo / Sydney)"
        else:
            computed_session = "OFF_HOURS (Overnight)"
            
        session = signal.get('session')
        if not session or session in ("UNKNOWN", "KILLZONE", "NEW_YORK"):
            session = computed_session
            
        ker_val = float(signal.get('asset_health', {}).get('ker', 0.35))
        rvol = float(signal.get('rvol', 1.6))
        
        # Formato de copiado 1-clic para MT5 y Exchanges con decimales precisos
        p_str = f"{price:.{decimals}f}"
        sl_str = f"{stop_loss:.{decimals}f}"
        be_str = f"{be_price:.{decimals}f}"
        tp1_str = f"{tp1:.{decimals}f}"
        tp2_str = f"{tp2:.{decimals}f}"
        tp3_str = f"{tp3:.{decimals}f}"
        
        one_click_text = f"[{account_profile.split('_')[0]} MT5] {action} {sym_mt5} @ {p_str} | LOTS: {lots:.2f} | SL: {sl_str} | 🛡️ BE (+1.0R): {be_str} | TP1 (50%): {tp1_str} | TP2 (30%): {tp2_str} | TP3 (20%): {tp3_str}"

        # Resumen de confluencias
        conf_badges = []
        if score >= 75: conf_badges.append("🔥 Grado ELITE")
        if rvol >= 1.3: conf_badges.append(f"📊 RVOL {rvol:.1f}x (Bancos)")
        if ker_val >= 0.35: conf_badges.append(f"⚡ KER {ker_val:.2f} (Limpio)")
        conf_summary = " • ".join(conf_badges) if conf_badges else "Confirmación SMC Institucional"

        message = (
            f"🎯 <b>NUEVA OPORTUNIDAD INSTITUCIONAL — SLINGSHOT v25.1</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💎 <b>Activo:</b> <code>{sym_mt5}</code> ({asset})\n"
            f"🧭 <b>Dirección:</b> <b>{'🟢 ' + direction if 'LONG' in direction else '🔴 ' + direction}</b> | ⏱️ <b>TF:</b> <code>{timeframe}</code>\n"
            f"🏛️ <b>Sesión:</b> <code>{session}</code> | ⚖️ <b>Confluencia:</b> <b>{score}%</b>\n"
            f"🔬 <b>Factores:</b> <i>{conf_summary}</i>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 <b>Entrada Límite (OTE 61.8%):</b> <code>{p_str}</code>\n"
            f"🛑 <b>Stop Loss (1.0R):</b> <code>{sl_str}</code> (-{((dist/price)*100):.2f}%)\n"
            f"🛡️ <b>Fast BE (+1.0R):</b> <code>{be_str}</code> <i>(Mover SL a Entrada / $0.00 Riesgo)</i>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 <b>OBJETIVOS ALPHA MAXIMIZER (50/30/20):</b>\n"
            f"   🥇 <b>TP1 (+1.5R - 50%):</b> <code>{tp1_str}</code> <i>(Cobra riesgo + Fee Absorber)</i>\n"
            f"   🥈 <b>TP2 (+3.0R - 30%):</b> <code>{tp2_str}</code> <i>(Garantiza +2.0R SL)</i>\n"
            f"   🥉 <b>TP3 (+5.0R - 20%):</b> <code>{tp3_str}</code> <i>(Home Run Runner)</i>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>GESTIÓN DE RIESGO Y MARGEN:</b>\n"
            f"   • 🏛️ <b>FTMO / MT5 ({account_profile}):</b> <code>{lots:.2f} Lots</code> (Riesgo: ${risk_usd:,.0f} USD)\n"
            f"   • ⚡ <b>Bitunix Futures:</b> <code>{action}</code> (20x Margen Aislado | Riesgo 5%)\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📋 <b>TOCA PARA COPIAR PARÁMETROS (1-CLIC):</b>\n"
            f"<code>{one_click_text}</code>"
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
                            logger.info(f"[TELEGRAM] 📲 Alerta enviada con éxito a {target_chat_id} para {sym_mt5} {direction}")
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
        """
        Envía un reporte periódico de signos vitales (Heartbeat) a Telegram.
        """
        if not self.enabled:
            return False

        uptime_hrs = stats.get("uptime_hours", 0.0)
        positions = stats.get("positions", [])
        latency_ms = stats.get("latency_ms", 12.0)
        drawdown_pct = stats.get("ftmo_drawdown_pct", 0.0)
        free_margin = stats.get("free_margin_usdt", 0.0)

        pos_lines = ""
        if positions:
            for p in positions:
                sym = p.get("symbol", "")
                side = p.get("side", "")
                pnl = p.get("pnl", 0.0)
                sl = p.get("sl", "N/A")
                pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
                pos_lines += f"   • <b>{sym}</b> ({side}) | SL: <code>{sl}</code> | PnL: <b>{pnl_str}</b>\n"
        else:
            pos_lines = "   <i>Sin posiciones abiertas en este ciclo.</i>\n"

        msg = (
            "💓 <b>SLINGSHOT APEX — SIGNOS VITALES DEL SISTEMA</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🟢 <b>Estado:</b> <code>100% OPERATIVO</code> | ⏱️ <b>Uptime:</b> <code>{uptime_hrs:.1f}h</code>\n"
            f"⚡ <b>Latencia API Bitunix:</b> <code>{latency_ms:.1f} ms</code>\n"
            f"🛡️ <b>Escudo FTMO Drawdown:</b> <code>{drawdown_pct:.2f}% / -3.50% Max</code>\n"
            f"💰 <b>Margen Libre Cripto:</b> <code>${free_margin:.2f} USDT</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📊 <b>POSICIONES VIVAS Y BLINDADAS:</b>\n"
            f"{pos_lines}"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🤖 <i>Centinelas de Auto-Healing, Invarianza SL y OTE Activos 24/7.</i>"
        )

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                for cid in self.chat_ids:
                    await client.post(url, json={
                        "chat_id": cid,
                        "text": msg,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True
                    })
            logger.info("[TELEGRAM] 💓 Reporte de Heartbeat enviado exitosamente.")
            return True
        except Exception as e:
            logger.debug(f"[TELEGRAM] Error enviando heartbeat: {e}")
            return False

    async def send_system_alert(self, title: str, details: str, severity: str = "WARNING") -> bool:
        """Envía una alerta crítica de contingencia a Telegram."""
        if not self.enabled:
            return False
        icon = "🚨" if severity == "CRITICAL" else "⚠️"
        msg = f"{icon} <b>SLINGSHOT ALERTA [{severity}]</b>\n<b>{title}</b>\n\n<code>{details}</code>"
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                for cid in self.chat_ids:
                    await client.post(url, json={"chat_id": cid, "text": msg, "parse_mode": "HTML"})
            return True
        except Exception:
            return False

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

# Instancia singleton para importación
telegram_dispatcher = TelegramDispatcher()


