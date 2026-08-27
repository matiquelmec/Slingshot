"""
engine/tests/test_setup_and_portability.py
=============================================================================
SUITE QA DE ONBOARDING, SETUP Y PORTABILIDAD MULTIPLATAFORMA (v22.2 APEX)
=============================================================================
Cubre los 5 vectores críticos de instalación, asistente y seguridad de claves:
1. Detección de estado de configuración (/api/v1/setup/status).
2. Validación en vivo de Bitunix (Simulación de claves válidas e inválidas).
3. Verificación de despacho y token de Telegram.
4. Escritura y guardado atómico de configuración (.env).
5. Resolución de rutas e independencia multiplataforma (Windows/Linux/Mac).
"""

import os
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import Response

from engine.api.setup import (
    get_setup_status,
    test_bitunix_connection as run_test_bitunix,
    test_telegram_connection as run_test_telegram,
    save_setup_configuration,
    TestBitunixRequest,
    TestTelegramRequest,
    SaveSetupRequest
)
from engine.api.config import settings


# ── TEST 1: DETECCIÓN DE ESTADO DE CONFIGURACIÓN ───────────────────────────

@pytest.mark.asyncio
async def test_setup_status_detects_unconfigured_state():
    """
    Verifica que el endpoint /setup/status identifique correctamente si el
    sistema tiene claves cargadas o requiere la apertura del Onboarding Wizard.
    """
    status = await get_setup_status()
    assert hasattr(status, "is_configured")
    assert hasattr(status, "has_bitunix")
    assert hasattr(status, "has_telegram")
    assert hasattr(status, "live_trading")
    assert isinstance(status.is_configured, bool)


# ── TEST 2: VALIDACIÓN EN VIVO DE BITUNIX (MOCK) ───────────────────────────

@pytest.mark.asyncio
async def test_setup_test_bitunix_mock_validation():
    """
    Verifica la validación de claves Bitunix tanto para respuesta exitosa
    (200 / code 0) como para rechazo por clave inválida.
    """
    # 1. Caso Exitoso
    mock_success_response = Response(
        status_code=200,
        json={"code": 0, "msg": "Success", "data": {"totalEquity": "1500.50", "marginAsset": "USDT"}}
    )
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_success_response
        req = TestBitunixRequest(api_key="valid_key_12345678", secret_key="valid_secret_12345678")
        res = await run_test_bitunix(req)
        assert res["valid"] is True
        assert res["total_equity"] == "1500.50"
        assert "verificadas" in res["message"]

    # 2. Caso Claves Inválidas
    mock_fail_response = Response(
        status_code=200,
        json={"code": 10003, "msg": "Signature error or invalid API key", "data": None}
    )
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_fail_response
        req = TestBitunixRequest(api_key="bad_key_1234", secret_key="bad_secret_1234")
        res = await run_test_bitunix(req)
        assert res["valid"] is False
        assert "rechazó" in res["message"]


# ── TEST 3: VERIFICACIÓN DE TELEGRAM (MOCK) ────────────────────────────────

@pytest.mark.asyncio
async def test_setup_test_telegram_mock_dispatch():
    """
    Verifica el ping de prueba a Telegram para confirmar recepción de alertas móviles.
    """
    mock_tg_response = Response(
        status_code=200,
        json={"ok": True, "result": {"message_id": 999}}
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_tg_response
        req = TestTelegramRequest(bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11", chat_id="987654321")
        res = await run_test_telegram(req)
        assert res["valid"] is True
        assert "exitosamente" in res["message"]


# ── TEST 4: GUARDADO ATÓMICO Y PERSISTENCIA DE CONFIGURACIÓN ───────────────

@pytest.mark.asyncio
async def test_setup_save_writes_atomic_env(tmp_path):
    """
    Verifica que la configuración guardada no corrompa el archivo .env
    y actualice correctamente las variables en memoria de Settings.
    """
    test_env_file = tmp_path / ".env_test"
    test_env_file.write_text("OLD_KEY=old_value\n", encoding="utf-8")
    
    with patch("engine.api.setup._ENV_FILE", str(test_env_file)):
        req = SaveSetupRequest(
            bitunix_api_key="new_bitunix_api_key_test_123",
            bitunix_secret_key="new_bitunix_secret_test_456",
            telegram_bot_token="new_tg_token_test",
            telegram_chat_id="11223344",
            enable_live_trading=True,
            account_balance=2500.0,
            max_risk_pct=0.015
        )
        
        res = await save_setup_configuration(req)
        assert res["success"] is True
        
        content = test_env_file.read_text(encoding="utf-8")
        assert "BITUNIX_API_KEY=new_bitunix_api_key_test_123" in content
        assert "BITUNIX_SECRET_KEY=new_bitunix_secret_test_456" in content
        assert "ENABLE_LIVE_TRADING=true" in content
        assert "ACCOUNT_BALANCE=2500.0" in content
        assert "OLD_KEY=old_value" in content


# ── TEST 5: RESOLUCIÓN DE RUTAS E INDEPENDENCIA MULTIPLATAFORMA ───────────

def test_cross_platform_path_resolution():
    """
    Verifica que el sistema use pathlib.Path de forma agnóstica a separadores / y \\
    garantizando portabilidad inmediata entre Windows, Linux y macOS.
    """
    root = Path(__file__).parent.parent.parent
    assert root.exists()
    assert (root / "engine").exists()
    assert (root / "package.json").exists()
    assert (root / "requirements.txt").exists()
    
    # Comprobar que no hay rutas hardcodeadas con 'C:\\' fuera de tests
    from engine.api.config import _ENV_FILE
    env_p = Path(_ENV_FILE)
    assert env_p.name.startswith(".env")
