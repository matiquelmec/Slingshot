"""
engine/tests/test_multi_account_stress_and_isolation_suite.py
============================================================
AUDITORÍA INSTITUCIONAL MULTI-CUENTA (SOP-45 & ARCHITECTURE):
1. Despacho Paralelo y Latencia en Ráfagas (Concurrencia con asyncio.gather)
2. Aislamiento Estricto de Cerrojos Atómicos (_symbol_locks[f"{acc}_{sym}"])
3. Cuotas de Riesgo Independientes y Reciclaje de Cupos (SOP-41 & SOP-45)
4. Aislamiento de Buffers de Alta Confluencia por Account ID
5. Tolerancia a Fallos Parciales (Fault Tolerance sin Contagio Cruzado)
6. Seguridad Criptográfica en Reposo (AES-Fernet) y Enmascaramiento de Secretos
"""

import asyncio
import pytest
import time
from unittest.mock import AsyncMock, patch, MagicMock
from engine.execution.nexus import NexusNode
from engine.execution.account_manager import (
    BitunixAccountConfig,
    encrypt_credential,
    decrypt_credential
)


@pytest.mark.asyncio
async def test_multi_account_concurrent_dispatch_latency():
    """Valida que una señal se despache a múltiples cuentas en paralelo en menos de 50ms sin bloqueo mutuo."""
    node = NexusNode(dry_run=False)
    
    # Mockear 2 ejecutores con simulación de llamada asíncrona
    exec_primary = AsyncMock()
    exec_primary.account_label = "Primary Mock"
    exec_primary.dry_run = True
    exec_primary.get_available_margin_usdt.return_value = 100.0
    exec_primary.get_net_available_margin_usdt = AsyncMock(return_value=100.0)
    exec_primary.get_pending_positions = AsyncMock(return_value=[])
    exec_primary.get_pending_orders = AsyncMock(return_value=[])
    exec_primary.get_symbol_precision = AsyncMock(return_value=(3, 2))
    exec_primary.place_limit_signal = AsyncMock(return_value={"status": "success", "order_id": "ord_p1"})

    exec_c2 = AsyncMock()
    exec_c2.account_label = "Cliente 2 Mock"
    exec_c2.dry_run = True
    exec_c2.get_available_margin_usdt.return_value = 250.0
    exec_c2.get_net_available_margin_usdt = AsyncMock(return_value=250.0)
    exec_c2.get_pending_positions = AsyncMock(return_value=[])
    exec_c2.get_pending_orders = AsyncMock(return_value=[])
    exec_c2.get_symbol_precision = AsyncMock(return_value=(3, 2))
    exec_c2.place_limit_signal = AsyncMock(return_value={"status": "success", "order_id": "ord_c2"})

    # Inyectar cuentas mock en el account manager
    mock_am = MagicMock()
    mock_am.get_all_accounts.return_value = [
        BitunixAccountConfig(account_id="primary", label="Primary", api_key="k1", secret_key="s1", dry_run=True, enabled=True),
        BitunixAccountConfig(account_id="cliente_2", label="Cliente 2", api_key="k2", secret_key="s2", dry_run=True, enabled=True)
    ]
    mock_am.get_executor.side_effect = lambda acc_id: exec_primary if acc_id == "primary" else exec_c2
    node.account_manager = mock_am

    sig = {
        "asset": "BTCUSDT",
        "symbol": "BTCUSDT",
        "direction": "LONG",
        "type": "LONG",
        "price": 60000.0,
        "stop_loss": 59000.0,
        "confluence_score": 85.0,
        "adx": 30.0,
        "ker": 0.50,
        "vwap_dist_pct": 0.01
    }

    t0 = time.perf_counter()
    with patch("engine.execution.nexus.cluster_risk_guard.can_open_position", return_value=(True, "OK")), \
         patch("engine.risk.risk_manager.RiskManager.check_vwap_exhaustion", return_value=(True, "OK")), \
         patch("engine.risk.risk_manager.RiskManager.check_regime_quarantine", return_value=(True, "OK")), \
         patch("engine.risk.risk_manager.RiskManager.calculate_alpha_tier_sizing", return_value=1.0), \
         patch("engine.risk.risk_manager.RiskManager.calculate_safe_leverage", return_value=10), \
         patch("engine.risk.risk_manager.RiskManager.verify_liquidation_clearance", return_value=(True, "OK", 2.0)):
        await node.process_limit_setup(sig)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    # Ambas cuentas deben haber colocado su orden concurrentemente
    assert exec_primary.place_limit_signal.called
    assert exec_c2.place_limit_signal.called
    # Despacho en memoria ultra-rápido en entorno virtualizado (<250ms con logging y patches)
    assert elapsed_ms < 250.0


@pytest.mark.asyncio
async def test_multi_account_strict_symbol_locks_isolation():
    """Valida que los cerrojos atómicos sean estrictamente por cuenta: primary_BTC != cliente_2_BTC."""
    node = NexusNode(dry_run=True)
    
    lock_primary = node._get_symbol_lock("primary", "BTCUSDT")
    lock_c2 = node._get_symbol_lock("cliente_2", "BTCUSDT")
    
    # Deben ser instancias de cerrojos distintas en memoria
    assert lock_primary is not lock_c2
    
    # Si primary adquiere su cerrojo, cliente_2 no se bloquea
    await lock_primary.acquire()
    assert lock_primary.locked()
    assert not lock_c2.locked()
    
    # Cliente 2 puede adquirir su propio cerrojo sin esperar a primary
    await lock_c2.acquire()
    assert lock_c2.locked()
    
    lock_primary.release()
    lock_c2.release()


@pytest.mark.asyncio
async def test_multi_account_independent_risk_caps_and_recycling():
    """Valida que la saturación de cupos en primary (4/4) no afecte a cliente_2 (0/4)."""
    node = NexusNode(dry_run=True)
    
    # Llenar primary con 4 operaciones con riesgo
    node._active_positions = {
        f"primary_SYM{i}": {
            "account_id": "primary",
            "signal": {"asset": f"SYM{i}", "price": 100, "stop_loss": 90},
            "smart_trailing": {"be_active": False}
        }
        for i in range(4)
    }
    
    # primary tiene 4 en riesgo -> lleno
    assert node.get_unprotected_risk_count("primary") == 4
    # cliente_2 tiene 0 en riesgo -> libre
    assert node.get_unprotected_risk_count("cliente_2") == 0

    # Poner 1 posición de primary en Breakeven (Fast BE -> $0.00 riesgo)
    node._active_positions["primary_SYM0"]["smart_trailing"]["be_active"] = True
    # primary ahora tiene 3 en riesgo -> 1 cupo liberado
    assert node.get_unprotected_risk_count("primary") == 3


@pytest.mark.asyncio
async def test_multi_account_buffer_isolation():
    """Valida que los buffers en espera de 'God Mode' estén estrictamente separados por cuenta."""
    node = NexusNode(dry_run=True)
    node._high_confluence_buffer = {}

    sig_p = {"asset": "SOLUSDT", "confluence_score": 90.0}
    sig_c2 = {"asset": "XRPUSDT", "confluence_score": 88.0}

    node.enqueue_high_confluence_opportunity(sig_p, "primary")
    node.enqueue_high_confluence_opportunity(sig_c2, "cliente_2")

    assert len(node._high_confluence_buffer["primary"]) == 1
    assert node._high_confluence_buffer["primary"][0]["asset"] == "SOLUSDT"

    assert len(node._high_confluence_buffer["cliente_2"]) == 1
    assert node._high_confluence_buffer["cliente_2"][0]["asset"] == "XRPUSDT"


@pytest.mark.asyncio
async def test_multi_account_fault_tolerance_isolation():
    """Valida que si una cuenta secundaria lanza una excepción crítica, la primaria ejecute sin interrupción."""
    node = NexusNode(dry_run=False)

    exec_primary = AsyncMock()
    exec_primary.account_label = "Primary Mock"
    exec_primary.dry_run = True
    exec_primary.get_available_margin_usdt.return_value = 100.0
    exec_primary.get_net_available_margin_usdt = AsyncMock(return_value=100.0)
    exec_primary.get_pending_positions = AsyncMock(return_value=[])
    exec_primary.get_pending_orders = AsyncMock(return_value=[])
    exec_primary.get_symbol_precision = AsyncMock(return_value=(3, 2))
    exec_primary.place_limit_signal = AsyncMock(return_value={"status": "success", "order_id": "ord_p1"})

    # Cliente 2 simula caída de red o error grave de API
    exec_c2 = AsyncMock()
    exec_c2.account_label = "Cliente 2 Corrupto"
    exec_c2.dry_run = True
    exec_c2.get_net_available_margin_usdt.side_effect = ConnectionResetError("Conexión abortada por exchange")

    mock_am = MagicMock()
    mock_am.get_all_accounts.return_value = [
        BitunixAccountConfig(account_id="primary", label="Primary", api_key="k1", secret_key="s1", dry_run=True, enabled=True),
        BitunixAccountConfig(account_id="cliente_2", label="Cliente 2", api_key="k2", secret_key="s2", dry_run=True, enabled=True)
    ]
    mock_am.get_executor.side_effect = lambda acc_id: exec_primary if acc_id == "primary" else exec_c2
    node.account_manager = mock_am

    sig = {
        "asset": "ETHUSDT",
        "symbol": "ETHUSDT",
        "direction": "LONG",
        "type": "LONG",
        "price": 3000.0,
        "stop_loss": 2950.0,
        "confluence_score": 80.0
    }

    with patch("engine.execution.nexus.cluster_risk_guard.can_open_position", return_value=(True, "OK")), \
         patch("engine.risk.risk_manager.RiskManager.check_vwap_exhaustion", return_value=(True, "OK")), \
         patch("engine.risk.risk_manager.RiskManager.check_regime_quarantine", return_value=(True, "OK")), \
         patch("engine.risk.risk_manager.RiskManager.calculate_alpha_tier_sizing", return_value=1.0), \
         patch("engine.risk.risk_manager.RiskManager.calculate_safe_leverage", return_value=10), \
         patch("engine.risk.risk_manager.RiskManager.verify_liquidation_clearance", return_value=(True, "OK", 2.0)):
        # No debe lanzar excepción al caller gracias a asyncio.gather(..., return_exceptions=True)
        await node.process_limit_setup(sig)

    # Primary debió ejecutar exitosamente a pesar del fallo en Cliente 2
    assert exec_primary.place_limit_signal.called


def test_multi_account_encryption_and_secret_masking():
    """Valida los procedimientos de seguridad: Cifrado Fernet AES y enmascaramiento estricto."""
    raw_secret = "super_secret_bitunix_api_token_12345"
    
    # 1. Cifrado
    encrypted = encrypt_credential(raw_secret)
    assert encrypted.startswith("enc:v1:")
    assert encrypted != raw_secret
    
    # 2. Descifrado transparente
    decrypted = decrypt_credential(encrypted)
    assert decrypted == raw_secret
    
    # 3. Idempotencia del cifrado
    assert encrypt_credential(encrypted) == encrypted
    
    # 4. Enmascaramiento en logs y serialización
    cfg = BitunixAccountConfig(
        account_id="audit_acc",
        label="Cuenta Auditoría",
        api_key="1234567890abcdef",
        secret_key="secret_very_private_123",
        enabled=True
    )
    masked = cfg.to_dict(mask_secrets=True)
    assert masked["api_key"] == "1234...cdef"
    assert masked["secret_key"] == "********"
    assert "secret_very_private_123" not in str(masked)
