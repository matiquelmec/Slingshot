"""
engine/api/setup.py
=============================================================================
API DE CONFIGURACIÓN INICIAL & VALIDACIÓN DE CREDENCIALES EN VIVO (v22.2 APEX)
=============================================================================
Gestiona el asistente de configuración inicial (Onboarding Wizard):
- Consulta de estado de configuración del sistema.
- Validación de API Key & Secret de Bitunix sin almacenar credenciales.
- Validación de Token y Chat ID de Telegram mediante ping de prueba.
- Guardado atómico y seguro del archivo .env.
"""

import os
import re
import hmac
import time
import httpx
import hashlib
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from engine.api.config import settings, _ENV_FILE
from engine.core.logger import logger

router = APIRouter(prefix="/setup", tags=["Setup & Onboarding"])


class SetupStatusResponse(BaseModel):
    is_configured: bool
    has_bitunix: bool
    has_binance: bool
    has_telegram: bool
    live_trading: bool
    account_balance: float
    max_risk_pct: float


class TestBitunixRequest(BaseModel):
    api_key: str
    secret_key: str


class TestTelegramRequest(BaseModel):
    bot_token: str
    chat_id: str


class SaveSetupRequest(BaseModel):
    bitunix_api_key: Optional[str] = None
    bitunix_secret_key: Optional[str] = None
    binance_api_key: Optional[str] = None
    binance_api_secret: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    enable_live_trading: bool = True
    account_balance: float = 1000.0
    max_risk_pct: float = 0.02


@router.get("/status", response_model=SetupStatusResponse)
async def get_setup_status():
    """
    Retorna el estado actual de configuración del sistema.
    """
    has_bitunix = bool(settings.BITUNIX_API_KEY and len(settings.BITUNIX_API_KEY) > 10 and settings.BITUNIX_SECRET_KEY and len(settings.BITUNIX_SECRET_KEY) > 10)
    has_binance = bool(settings.BINANCE_API_KEY and len(settings.BINANCE_API_KEY) > 10)
    has_telegram = bool(settings.TELEGRAM_BOT_TOKEN and len(settings.TELEGRAM_BOT_TOKEN) > 10)
    
    # Se considera configurado si tiene al menos Bitunix configurado
    is_configured = has_bitunix
    
    return SetupStatusResponse(
        is_configured=is_configured,
        has_bitunix=has_bitunix,
        has_binance=has_binance,
        has_telegram=has_telegram,
        live_trading=bool(settings.ENABLE_LIVE_TRADING),
        account_balance=float(settings.ACCOUNT_BALANCE),
        max_risk_pct=float(settings.MAX_RISK_PCT)
    )


@router.post("/test-bitunix")
async def test_bitunix_connection(req: TestBitunixRequest):
    """
    Prueba en vivo la validez de la API Key y Secret Key de Bitunix llamando a su API de balance.
    SOP-07: Las claves NUNCA se imprimen en logs.
    """
    api_key = req.api_key.strip()
    secret_key = req.secret_key.strip()
    
    if not api_key or not secret_key:
        raise HTTPException(status_code=400, detail="API Key y Secret Key son requeridas.")
    
    masked_key = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "***"
    logger.info(f"🧪 [SETUP] Probando credenciales de Bitunix para clave: {masked_key}")
    
    # Construcción de la firma Bitunix
    timestamp = str(int(time.time() * 1000))
    nonce = os.urandom(8).hex()
    query_str = ""
    body_str = ""
    
    # SHA256 digest del query + body
    digest_input = query_str + body_str
    digest = hashlib.sha256(digest_input.encode("utf-8")).hexdigest()
    
    # HMAC-SHA256 signature
    sign_payload = f"{api_key}{nonce}{timestamp}{digest}"
    signature = hmac.new(secret_key.encode("utf-8"), sign_payload.encode("utf-8"), hashlib.sha256).hexdigest()
    
    headers = {
        "api-key": api_key,
        "nonce": nonce,
        "timestamp": timestamp,
        "sign": signature,
        "Content-Type": "application/json"
    }
    
    url = "https://fapi.bitunix.com/api/v1/futures/account"
    
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, headers=headers)
            data = resp.json()
            
            if resp.status_code == 200 and data.get("code") == 0:
                account_data = data.get("data", {})
                margin_asset = account_data.get("marginAsset", "USDT")
                total_equity = account_data.get("totalEquity", "0")
                logger.info(f"✅ [SETUP] Bitunix autenticado con éxito. Total Equity: ${total_equity} {margin_asset}")
                return {
                    "valid": True,
                    "message": "Credenciales de Bitunix válidas y verificadas.",
                    "total_equity": total_equity,
                    "margin_asset": margin_asset
                }
            else:
                msg = data.get("msg", "Error de autenticación en Bitunix")
                logger.warning(f"❌ [SETUP] Bitunix rechazó credenciales: {msg}")
                return {
                    "valid": False,
                    "message": f"Bitunix rechazó las claves: {msg}"
                }
    except Exception as e:
        logger.error(f"💥 [SETUP] Error de conexión probando Bitunix: {e}")
        return {
            "valid": False,
            "message": f"Error de red al conectar con Bitunix: {str(e)}"
        }


@router.post("/test-telegram")
async def test_telegram_connection(req: TestTelegramRequest):
    """
    Envía un mensaje de prueba al chat de Telegram para validar el bot y chat ID.
    """
    bot_token = req.bot_token.strip()
    chat_id = req.chat_id.strip()
    
    if not bot_token or not chat_id:
        raise HTTPException(status_code=400, detail="Bot Token y Chat ID son requeridos.")
    
    logger.info("🧪 [SETUP] Probando despacho de alerta de prueba a Telegram...")
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": "🛡️ <b>[SLINGSHOT APEX] Vinculación Exitosa</b>\n\nTu terminal de trading cuantitativo ha verificado la conexión con Telegram correctamente. Recibirás aquí todas las alertas de alta confluencia y ejecuciones.",
        "parse_mode": "HTML"
    }
    
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(url, json=payload)
            data = resp.json()
            if resp.status_code == 200 and data.get("ok"):
                logger.info("✅ [SETUP] Mensaje de prueba de Telegram enviado exitosamente.")
                return {
                    "valid": True,
                    "message": "Mensaje de prueba enviado exitosamente a Telegram."
                }
            else:
                desc = data.get("description", "Error de Telegram")
                logger.warning(f"❌ [SETUP] Telegram rechazó el mensaje: {desc}")
                return {
                    "valid": False,
                    "message": f"Telegram rechazó el envío: {desc}"
                }
    except Exception as e:
        logger.error(f"💥 [SETUP] Error conectando con Telegram: {e}")
        return {
            "valid": False,
            "message": f"Error de red conectando con Telegram: {str(e)}"
        }


@router.post("/save")
async def save_setup_configuration(req: SaveSetupRequest):
    """
    Guarda atómicamente la configuración en el archivo .env y recarga settings en memoria.
    """
    env_path = Path(_ENV_FILE)
    
    # Leer el .env existente o crearlo a partir de una plantilla
    existing_content = ""
    if env_path.exists():
        try:
            existing_content = env_path.read_text(encoding="utf-8")
        except Exception:
            pass
    
    updates = {}
    if req.bitunix_api_key:
        updates["BITUNIX_API_KEY"] = req.bitunix_api_key.strip()
    if req.bitunix_secret_key:
        updates["BITUNIX_SECRET_KEY"] = req.bitunix_secret_key.strip()
    if req.binance_api_key:
        updates["BINANCE_API_KEY"] = req.binance_api_key.strip()
    if req.binance_api_secret:
        updates["BINANCE_API_SECRET"] = req.binance_api_secret.strip()
    if req.telegram_bot_token:
        updates["TELEGRAM_BOT_TOKEN"] = req.telegram_bot_token.strip()
    if req.telegram_chat_id:
        updates["TELEGRAM_CHAT_ID"] = req.telegram_chat_id.strip()
    
    updates["ENABLE_LIVE_TRADING"] = "true" if req.enable_live_trading else "false"
    updates["ACCOUNT_BALANCE"] = str(req.account_balance)
    updates["MAX_RISK_PCT"] = str(req.max_risk_pct)
    
    # Actualizar o agregar líneas en el .env
    lines = existing_content.splitlines()
    new_lines = []
    found_keys = set()
    
    for line in lines:
        matched = False
        for k, v in updates.items():
            if line.startswith(f"{k}=") or re.match(rf"^\s*#?\s*{k}=", line):
                new_lines.append(f"{k}={v}")
                found_keys.add(k)
                matched = True
                break
        if not matched:
            new_lines.append(line)
            
    for k, v in updates.items():
        if k not in found_keys:
            new_lines.append(f"{k}={v}")
            
    final_env_text = "\n".join(new_lines) + "\n"
    
    # Escritura atómica mediante archivo temporal
    tmp_path = env_path.with_suffix(".tmp")
    try:
        tmp_path.write_text(final_env_text, encoding="utf-8")
        tmp_path.replace(env_path)
        logger.info(f"💾 [SETUP] Configuración guardada atómicamente en {env_path}")
    except Exception as e:
        logger.error(f"💥 [SETUP] Error guardando archivo .env: {e}")
        raise HTTPException(status_code=500, detail=f"Error escribiendo archivo de configuración: {e}")
    
    # Recargar variables de settings en tiempo de ejecución
    if req.bitunix_api_key:
        settings.BITUNIX_API_KEY = req.bitunix_api_key.strip()
    if req.bitunix_secret_key:
        settings.BITUNIX_SECRET_KEY = req.bitunix_secret_key.strip()
    if req.binance_api_key:
        settings.BINANCE_API_KEY = req.binance_api_key.strip()
    if req.binance_api_secret:
        settings.BINANCE_API_SECRET = req.binance_api_secret.strip()
    if req.telegram_bot_token:
        settings.TELEGRAM_BOT_TOKEN = req.telegram_bot_token.strip()
    if req.telegram_chat_id:
        settings.TELEGRAM_CHAT_ID = req.telegram_chat_id.strip()
    settings.ENABLE_LIVE_TRADING = req.enable_live_trading
    settings.ACCOUNT_BALANCE = req.account_balance
    settings.MAX_RISK_PCT = req.max_risk_pct
    
    return {
        "success": True,
        "message": "Configuración guardada y activada con éxito. Slingshot Apex está listo para operar."
    }
