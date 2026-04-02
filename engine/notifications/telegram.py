"""
Capa 6: Sistema de Notificaciones — Bot de Telegram.
Envía alertas ricas en formato Markdown cuando Slingshot genera señales reales.
"""
import httpx
import asyncio
from datetime import datetime
from engine.api.config import settings

TELEGRAM_BOT_TOKEN = settings.TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID   = settings.TELEGRAM_CHAT_ID

# URL base de la Telegram Bot API
_BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def _is_configured() -> bool:
    """Verifica que las credenciales no están vacías antes de intentar enviar."""
    return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)


def _format_signal_message(signal: dict, asset: str, regime: str, strategy: str) -> str:
    """
    Construye el texto del mensaje con formato Markdown de Telegram.
    Ejemplo:
    🚨 SLINGSHOT — SEÑAL DETECTADA
    📈 LONG en BTCUSDT @ $95,230.50
    ...
    """
    sig_type = signal.get('type', 'SEÑAL')
    price = signal.get('price', 0)
    trigger = signal.get('trigger', 'N/A')
    risk_usd = signal.get('risk', 'N/A')
    position_usd = signal.get('position', 'N/A')

    # Emoji dinámico según dirección
    if 'LONG' in sig_type.upper():
        direction_icon = '📈'
        color_icon = '🟢'
    elif 'SHORT' in sig_type.upper():
        direction_icon = '📉'
        color_icon = '🔴'
    else:
        direction_icon = '⚡'
        color_icon = '🟡'

    ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')

    message = (
        f"🎯 *SLINGSHOT — SEÑAL DETECTADA*\n\n"
        f"{direction_icon} *{sig_type.split('(')[0].strip()}* en `{asset}`\n"
        f"💰 Precio de Entrada: `${price:,.2f}`\n\n"
        f"🗺️ Régimen: `{regime}`\n"
        f"🤖 Estrategia: `{strategy}`\n"
        f"🔬 Trigger: _{trigger}_\n\n"
        f"🛡️ Riesgo: `${risk_usd}` · Posición: `${position_usd}`\n"
        f"📊 R:R Mínimo: `3:1`\n\n"
        f"🕒 _{ts}_\n"
        f"\\-\\-\\-\n"
        f"_La precisión es la única respuesta válida ante la fuerza bruta\\._"
    )
    return message


async def send_signal_async(signal: dict, asset: str, regime: str, strategy: str) -> bool:
    """
    Envía una notificación de señal al bot de Telegram (versión async para FastAPI).
    Retorna True si el envío fue exitoso.
    """
    if not _is_configured():
        print("[TELEGRAM] ⚠️  Bot no configurado (TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID vacíos).")
        return False

    text = _format_signal_message(signal, asset, regime, strategy)
    url = f"{_BASE_URL}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "MarkdownV2",
        "disable_web_page_preview": True,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                print(f"[TELEGRAM] ✅ Señal enviada: {signal.get('type')} @ ${signal.get('price')}")
                return True
            else:
                print(f"[TELEGRAM] ❌ Error HTTP {resp.status_code}: {resp.text}")
                return False
    except Exception as e:
        print(f"[TELEGRAM] ❌ Excepción al enviar: {e}")
        return False


async def send_drift_alert_async(drift_info: dict) -> bool:
    """Notifica al trader cuando el modelo ML tiene drift significativo."""
    if not _is_configured():
        return False

    # Visual indicators based on level
    level = drift_info.get('level', 'MODERATE')
    icon  = "🚨" if level == "SEVERE" else "⚠️"
    asset = drift_info.get('asset', 'N/A').replace('-', '\\-').replace('_', '\\_') # MarkdownV2 safe

    # Escaping features for MarkdownV2 backticks
    feats  = drift_info.get('affected_features', 'N/A').replace('_', '\\_')

    text = (
        f"{icon} *SLINGSHOT — DRIFT ML [{asset}]*\n\n"
        f"Salud del modelo: *{level}*\n\n"
        f"📊 Features con PSI alto: `{feats}`\n"
        f"📉 Accuracy rolling: `{drift_info.get('rolling_accuracy', 'N/A')}%` \n"
        f"🧠 PSI Máximo: `{drift_info.get('psi_max', 'N/A')}`\n\n"
        f"🛡️ *Acción recomendada:*\n"
        f"_{drift_info.get('recommendation', 'Revisar modelo')}_"
    ).replace('.', '\\.')

    url = f"{_BASE_URL}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "MarkdownV2"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            return resp.status_code == 200
    except Exception as e:
        print(f"[TELEGRAM] ❌ Error en drift alert: {e}")
        return False


if __name__ == "__main__":
    # Test de conexión
    async def _test():
        test_signal = {
            'type': 'LONG 🟢 (TREND PULLBACK)',
            'price': 95230.50,
            'trigger': 'EMA 50 + Fibo 0.618 Confluencia',
            'risk': 10.0,
            'position': 200.0
        }
        ok = await send_signal_async(test_signal, 'BTCUSDT', 'MARKUP', 'TrendFollowingStrategy')
        print("Test OK" if ok else "Test FALLIDO — revisar credenciales en .env")

    asyncio.run(_test())
