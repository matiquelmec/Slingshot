"""
Capa 6: Sistema de Notificaciones â€” Bot de Telegram.
EnvÃ­a alertas ricas en formato Markdown cuando Slingshot genera seÃ±ales reales.
Soporta mÃºltiples destinatarios (TELEGRAM_CHAT_ID separado por comas).
"""
from engine.core.logger import logger
import httpx
import asyncio
from datetime import datetime
from engine.api.config import settings

TELEGRAM_BOT_TOKEN = settings.TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID_RAW = str(settings.TELEGRAM_CHAT_ID or "")

# Extraer lista limpia de IDs de chat (soporta enteros, negativos de grupos, y comas)
TELEGRAM_CHAT_IDS = [cid.strip() for cid in TELEGRAM_CHAT_ID_RAW.split(",") if cid.strip()]

# URL base de la Telegram Bot API
_BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def _is_configured() -> bool:
    """Verifica que las credenciales no estÃ©n vacÃ­as antes de intentar enviar."""
    return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_IDS)


def _format_signal_message(signal: dict, asset: str, regime: str, strategy: str) -> str:
    """Construye el texto del mensaje con formato Markdown de Telegram."""
    sig_type = signal.get('type', 'SEÃ‘AL')
    price = signal.get('price', 0)
    trigger = signal.get('trigger', 'N/A')
    risk_usd = signal.get('risk', 'N/A')
    position_usd = signal.get('position', 'N/A')

    if 'LONG' in sig_type.upper():
        direction_icon = 'ðŸŸ¢'
        color_icon = 'ðŸš€'
    else:
        direction_icon = 'ðŸ”´'
        color_icon = 'ðŸ”»'

    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    lines = [
        f"{color_icon} *SLINGSHOT â€” SEÃ‘AL DETECTADA*",
        f"{direction_icon} *{sig_type}* en *{asset}* @ `${price:,.2f}`",
        f"â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”",
        f"ðŸ“Š *Estrategia:* `{strategy}`",
        f"ðŸŒ *RÃ©gimen:* `{regime}`",
        f"âš¡ *Trigger:* `{trigger}`",
    ]

    if risk_usd != 'N/A' and isinstance(risk_usd, (int, float)):
        lines.append(f"ðŸ›¡ *Riesgo Est:* `${risk_usd:,.2f}`")
    if position_usd != 'N/A' and isinstance(position_usd, (int, float)):
        lines.append(f"ðŸ’° *PosiciÃ³n Est:* `${position_usd:,.2f}`")

    lines.extend([
        f"â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”",
        f"â° `{now_str}`",
        f"ðŸ¤– _Slingshot Institutional Engine_",
    ])

    return "\n".join(lines)


async def send_telegram_alert(signal: dict, asset: str, regime: str, strategy: str) -> bool:
    """EnvÃ­a la alerta de seÃ±al a todos los canales/chats configurados en Telegram."""
    if not _is_configured():
        logger.debug("[TELEGRAM] Bot no configurado (TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID vacÃ­os).")
        return False

    message_text = _format_signal_message(signal, asset, regime, strategy)
    return await send_raw_telegram_message(message_text)


async def send_raw_telegram_message(text: str) -> bool:
    """EnvÃ­a un mensaje de texto a todos los chats de Telegram registrados."""
    if not _is_configured():
        return False

    success_all = True
    async with httpx.AsyncClient(timeout=10.0) as client:
        for cid in TELEGRAM_CHAT_IDS:
            payload = {
                "chat_id": cid,
                "text": text,
                "parse_mode": "Markdown",
            }
            try:
                resp = await client.post(f"{_BASE_URL}/sendMessage", json=payload)
                if resp.status_code == 200:
                    logger.info(f"[TELEGRAM] Alerta enviada con Ã©xito a chat {cid}")
                else:
                    logger.warning(f"[TELEGRAM] Error {resp.status_code} enviando a {cid}: {resp.text}")
                    # Intento de fallback sin Markdown si hubo error de parseo
                    payload.pop("parse_mode", None)
                    await client.post(f"{_BASE_URL}/sendMessage", json=payload)
            except Exception as exc:
                logger.error(f"[TELEGRAM] ExcepciÃ³n al enviar mensaje a {cid}: {exc}")
                success_all = False

    return success_all

async def send_signal_async(signal: dict, asset: str, regime: str, strategy: str) -> bool:
    """Alias de compatibilidad heredada para tests y endpoints FastAPI."""
    return await send_telegram_alert(signal, asset, regime, strategy)
