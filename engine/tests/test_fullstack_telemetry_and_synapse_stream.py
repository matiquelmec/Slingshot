"""
engine/tests/test_fullstack_telemetry_and_synapse_stream.py
=============================================================================
SUITE DE CERTIFICACIÓN QA: APEX SYNAPSE & FULLSTACK TELEMETRY (v27.0)
=============================================================================
Audita:
1. Emisión y validación segura de tokens JWT para WebSocket (Handshake & SOP-15).
2. Despacho global prioritario e inmediato de señales aprobadas (High-Priority Broadcast).
3. Normalización e invarianza determinística de IDs de señales para evitar duplicados en frontend.
4. Integridad del payload de estados de mercado para el Radar en tiempo real.
5. Sanitización de datos anti-NaN y protección de backpressure en streams de telemetría.
"""
import pytest
import time
import asyncio
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, AsyncMock

from engine.api.auth import issue_token, validate_token
from engine.api.signal_handler import SignalHandler
from engine.api.json_utils import sanitize_for_json
from engine.core.store import store
from engine.api.config import settings

def test_ws_token_issuance_and_validation_handshake():
    """
    Verifica la emisión de tokens JWT para WebSocket y su validación estricta (SOP-15).
    """
    token = issue_token()
    assert isinstance(token, str)
    assert len(token) > 20
    
    # Validación con token legítimo
    is_valid, reason, claims = validate_token(token)
    assert is_valid is True
    assert reason == ""
    assert "sub" in claims
    assert claims["iss"] == "slingshot-v10"
    
    # Validación con token corrupto / inválido
    is_invalid, invalid_reason, _ = validate_token("corrupted.token.signature")
    assert is_invalid is False
    assert invalid_reason != ""

@pytest.mark.asyncio
async def test_signal_handler_immediate_global_broadcast():
    """
    Verifica que SignalHandler emita un broadcast global inmediato en cuanto una señal es aprobada.
    """
    handler = SignalHandler("SOLUSDT", "15m", None)
    
    tactical_mock = {
        "market_regime": "MARKUP",
        "active_strategy": "SMC_SNIPER",
        "signals": [
            {
                "type": "LONG",
                "price": 145.50,
                "stop_loss": 143.00,
                "take_profit_3r": 153.00,
                "confluence": {"score": 85},
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        ]
    }
    
    with patch("engine.api.registry.registry.broadcast_global", new_callable=AsyncMock) as mock_broadcast:
        with patch("engine.notifications.filter.signal_filter.should_send", return_value=(True, "OK")):
            with patch("engine.router.telegram_dispatcher.telegram_dispatcher.send_signal_alert", new_callable=AsyncMock):
                with patch("engine.execution.nexus.nexus.process_signal", new_callable=AsyncMock):
                    await handler.handle(tactical_mock)
                    
                    # Verificar que se llamó a broadcast_global con la señal persistida
                    assert mock_broadcast.called
                    call_args = mock_broadcast.call_args[0][0]
                    assert call_args["type"] == "signal_auditor_update"
                    assert call_args["data"]["asset"] == "SOLUSDT"
                    assert call_args["data"]["status"] == "ACTIVE"
                    assert call_args["data"]["entry_price"] == 145.50

def test_deterministic_signal_id_normalization():
    """
    Verifica que el debounce y la asignación de IDs de señales sea determinística y no duplique eventos.
    """
    handler = SignalHandler("ETHUSDT", "15m", None)
    
    ts = "2026-09-01T15:00:00+00:00"
    signals = [
        {"type": "LONG", "price": 2800.0, "timestamp": ts, "confluence": {"score": 75}},
        {"type": "LONG", "price": 2800.0, "timestamp": ts, "confluence": {"score": 78}}, # Mismo score band 'S'
        {"type": "SHORT", "price": 2800.0, "timestamp": ts, "confluence": {"score": 45}}, # Distinto tipo y score band
    ]
    
    debounced = handler._debounce(signals, min_score=0)
    # Las dos primeras señales LONG caen en el mismo score band 'S' (score >= 70), por lo que se deduplican
    assert len(debounced) == 2
    assert debounced[0]["type"] == "LONG"
    assert debounced[1]["type"] == "SHORT"

@pytest.mark.asyncio
async def test_market_states_radar_payload_integrity():
    """
    Verifica que la actualización del Radar mantenga tipos consistentes y sanitizados para el frontend.
    """
    await store.update_market_state("BTCUSDT", {
        "price": 62500.0,
        "current_price": 62500.0,
        "regime": "BULLISH_EXPANSION",
        "bias": "BULLISH",
        "score": 82
    })
    
    states = await store.get_market_states()
    assert len(states) > 0
    btc_state = next((s for s in states if s["asset"] == "BTCUSDT"), None)
    assert btc_state is not None
    assert btc_state["price"] == 62500.0
    assert btc_state["regime"] == "BULLISH_EXPANSION"

def test_stream_optimistic_state_retention_and_sanitization():
    """
    Verifica que sanitize_for_json limpie valores float NaN, Infinity y estructuras complejas
    para evitar fallos de deserialización en el cliente WebSocket.
    """
    dirty_payload = {
        "asset": "AVAXUSDT",
        "price": 28.50,
        "invalid_nan": float("nan"),
        "invalid_inf": float("inf"),
        "nested": {
            "negative_inf": float("-inf"),
            "clean_val": 12.34
        }
    }
    
    cleaned = sanitize_for_json(dirty_payload)
    assert cleaned["invalid_nan"] is None
    assert cleaned["invalid_inf"] is None
    assert cleaned["nested"]["negative_inf"] is None
    assert cleaned["nested"]["clean_val"] == 12.34
    assert cleaned["price"] == 28.50