"""
Capa 6: Adaptador de compatibilidad hacia TelegramDispatcher (SOP-132).
Mantiene compatibilidad de firma con tests heredados sin duplicar lógica HTTP ni exponer datos financieros.
"""
from datetime import datetime
import httpx
from engine.core.logger import logger
from engine.api.config import settings

TELEGRAM_BOT_TOKEN = settings.TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID_RAW = str(settings.TELEGRAM_CHAT_ID or "")
TELEGRAM_CHAT_IDS = [cid.strip() for cid in TELEGRAM_CHAT_ID_RAW.split(",") if cid.strip()]
_BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def _is_configured() -> bool:
    return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_IDS)


def _format_signal_message(signal: dict, asset: str, regime: str, strategy: str) -> str:
    """Formatea un mensaje técnico minimalista sin datos de balance o USD."""
    sig_type = str(signal.get("type", "SEÑAL")).upper()
    price = float(signal.get("price", 0) or 0)
    icon = "🟢" if "LONG" in sig_type else "🔴"
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    return (
        f"{icon} *{sig_type}* en *{asset}* @ `{price:,.2f}`\n"
        f"Estrategia: `{strategy}` | Régimen: `{regime}` | `{now_str}`"
    )


async def send_telegram_alert(signal: dict, asset: str, regime: str, strategy: str) -> bool:
    from engine.router.telegram_dispatcher import telegram_dispatcher
    enriched = dict(signal)
    enriched.setdefault("asset", asset)
    return await telegram_dispatcher.send_signal_alert(enriched)


async def send_raw_telegram_message(text: str) -> bool:
    if not _is_configured():
        return False
    success_all = True
    async with httpx.AsyncClient(timeout=10.0) as client:
        for cid in TELEGRAM_CHAT_IDS:
            payload = {"chat_id": cid, "text": text, "parse_mode": "Markdown"}
            try:
                resp = await client.post(f"{_BASE_URL}/sendMessage", json=payload)
                if resp.status_code != 200:
                    payload.pop("parse_mode", None)
                    await client.post(f"{_BASE_URL}/sendMessage", json=payload)
            except Exception as exc:
                logger.error(f"[TELEGRAM] Excepción al enviar mensaje a {cid}: {exc}")
                success_all = False
    return success_all


async def send_signal_async(signal: dict, asset: str, regime: str, strategy: str) -> bool:
    return await send_telegram_alert(signal, asset, regime, strategy)
