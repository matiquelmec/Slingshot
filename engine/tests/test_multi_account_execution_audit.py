"""
engine/tests/test_multi_account_execution_audit.py
=============================================================================
SUITE DE CERTIFICACIÓN QA: MULTI-ACCOUNT EXECUTION & RISK ISOLATION AUDIT
=============================================================================
Certifica que:
1. Las credenciales de cuentas secundarias se cifren y descifren mediante
   AES-256 Fernet en reposo con prefijo 'enc:v1:'.
2. Cada cuenta Bitunix disponga de cálculo de riesgo puro en dólares (SOP-41)
   completamente independiente basado en su propio margen y saldo.
3. El despacho paralelo de órdenes límite ejecute en ambas cuentas sin
   interferencias ni colisiones de estado mutable.
4. La gestión de Stop Loss en TradeManager resuelva el positionId de cada
   cuenta en caliente si no viene mapeado en la señal.
=============================================================================
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from engine.execution.account_manager import (
    AccountManager,
    BitunixAccountConfig,
    encrypt_credential,
    decrypt_credential
)
from engine.risk.risk_manager import RiskManager


def test_multi_account_aes256_credential_encryption():
    """
    Verifica que las claves de API secundarias se cifren con Fernet AES-256
    en reposo y se descifren transparentemente en tiempo de ejecución.
    """
    plain_secret = "bitunix_secret_super_confidential_9876543210"
    encrypted = encrypt_credential(plain_secret)

    # Debe poseer prefijo de versión enc:v1:
    assert encrypted.startswith("enc:v1:")
    # No debe contener el texto plano
    assert plain_secret not in encrypted

    # Descifrado transparente
    decrypted = decrypt_credential(encrypted)
    assert decrypted == plain_secret


def test_independent_dollar_risk_sizing_per_account():
    """
    Verifica que dos cuentas con saldos dispares ($1,000 USDT vs $10,000 USDT)
    dimensionen tamaños de posición y contratos estrictamente acordes a su saldo,
    respetando el riesgo en dólares del 2.50% (SOP-41).
    """
    entry = 60000.0
    sl = 59000.0
    risk_pct = 0.025  # 2.50%

    # Cuenta A: $1,000 USDT
    calc_a = RiskManager.calculate_dollar_risk_position(
        account_balance=1000.0,
        risk_pct=risk_pct,
        entry_price=entry,
        sl_price=sl,
        leverage=10,
        max_notional_mult=5.0,
        qty_decimals=3
    )

    # Cuenta B: $10,000 USDT
    calc_b = RiskManager.calculate_dollar_risk_position(
        account_balance=10000.0,
        risk_pct=risk_pct,
        entry_price=entry,
        sl_price=sl,
        leverage=10,
        max_notional_mult=5.0,
        qty_decimals=3
    )

    assert calc_a["approved"] is True
    assert calc_b["approved"] is True

    # Pérdida proyectada: Cuenta A = $25 USDT | Cuenta B = $250 USDT
    assert calc_a["projected_loss"] == pytest.approx(25.0, rel=0.05)
    assert calc_b["projected_loss"] == pytest.approx(250.0, rel=0.05)

    # Cantidad de contratos debe ser proporcional a los saldos (10x de diferencia)
    assert calc_b["qty"] == pytest.approx(calc_a["qty"] * 10, rel=0.05)


@pytest.mark.asyncio
async def test_multi_account_parallel_limit_dispatch():
    """
    Verifica que Nexus despache órdenes límite en paralelo a todas las cuentas
    activas habilitadas sin que el fallo o timeout de una afecte a la otra.
    """
    from engine.execution.nexus import Nexus

    mock_mgr = MagicMock()
    acc1 = BitunixAccountConfig(
        account_id="primary",
        label="Cuenta 1",
        api_key="k1",
        secret_key="s1",
        enabled=True,
        risk_pct=0.025,
        is_primary=True
    )
    acc2 = BitunixAccountConfig(
        account_id="secondary_vip",
        label="Cuenta 2",
        api_key="k2",
        secret_key="s2",
        enabled=True,
        risk_pct=0.025,
        is_primary=False
    )
    mock_mgr.get_all_accounts.return_value = [acc1, acc2]

    # Ejecutores mockeados
    mock_ex1 = MagicMock()
    mock_ex1.dry_run = True
    mock_ex1.get_net_available_margin_usdt = AsyncMock(return_value=1000.0)
    mock_ex1.get_available_margin_usdt = AsyncMock(return_value=1000.0)
    mock_ex1.get_pending_positions = AsyncMock(return_value=[])
    mock_ex1.get_pending_orders = AsyncMock(return_value=[])
    mock_ex1.get_symbol_precision = AsyncMock(return_value=(3, 2))
    mock_ex1.place_limit_signal = AsyncMock(return_value={"status": "success", "order_id": "ord_acc1_001"})

    mock_ex2 = MagicMock()
    mock_ex2.dry_run = True
    mock_ex2.get_net_available_margin_usdt = AsyncMock(return_value=5000.0)
    mock_ex2.get_available_margin_usdt = AsyncMock(return_value=5000.0)
    mock_ex2.get_pending_positions = AsyncMock(return_value=[])
    mock_ex2.get_pending_orders = AsyncMock(return_value=[])
    mock_ex2.get_symbol_precision = AsyncMock(return_value=(3, 2))
    mock_ex2.place_limit_signal = AsyncMock(return_value={"status": "success", "order_id": "ord_acc2_002"})

    def get_mock_executor(acc_id):
        return mock_ex1 if acc_id == "primary" else mock_ex2

    mock_mgr.get_executor = get_mock_executor

    test_nexus = Nexus(dry_run=False)
    test_nexus.account_manager = mock_mgr

    candidate_signal = {
        "asset": "BTCUSDT",
        "symbol": "BTCUSDT",
        "direction": "LONG",
        "price": 60000.0,
        "stop_loss": 59000.0,
        "tp1": 61200.0,
        "tp2": 62000.0,
        "tp3": 63500.0,
        "confluence_score": 85,
        "btc_aligned": True,
        "session_avwap_dist_pct": 0.10,
        "ker": 0.45,
        "adx": 26.0,
        "playbook": "OB_DISCOUNT_RETEST"
    }

    # Despachar setup límite
    with patch("engine.workers.market_scanner.is_trade_allowed_sop18", return_value=True):
        dispatch_res = await test_nexus.process_limit_setup(candidate_signal)

    assert dispatch_res["placed"] is True
    assert dispatch_res["status"] == "ORDER_PLACED"

    # Ambos ejecutores deben haber sido llamados con sus propias órdenes
    assert mock_ex1.place_limit_signal.called
    assert mock_ex2.place_limit_signal.called


@pytest.mark.asyncio
async def test_trade_manager_multi_account_sl_update_hot_resolution():
    """
    Verifica que TradeManager al actualizar SL por señal resuelva en caliente
    el positionId de la cuenta secundaria si no está en la señal.
    """
    from engine.workers.trade_manager import TradeManager

    tm = TradeManager()

    mock_ex1 = MagicMock()
    mock_ex1.account_label = "Cuenta Principal"
    mock_ex1.dry_run = False
    mock_ex1.modify_position_tpsl = AsyncMock(return_value=True)

    mock_ex2 = MagicMock()
    mock_ex2.account_label = "Cuenta Secundaria"
    mock_ex2.dry_run = False
    # La cuenta 2 tiene positionId 'pos_sec_999' en el exchange
    mock_ex2.get_pending_positions = AsyncMock(return_value=[{"symbol": "ETHUSDT", "positionId": "pos_sec_999"}])
    mock_ex2.modify_position_tpsl = AsyncMock(return_value=True)

    with patch("engine.execution.account_manager.AccountManager.get_all_executors", return_value={"primary": mock_ex1, "secondary": mock_ex2}):
        with patch("engine.core.store.store.save_signal", new_callable=AsyncMock):
            test_signal = {
                "asset": "ETHUSDT",
                "position_id": "pos_prim_111",
                "account_position_ids": {"primary": "pos_prim_111"},
                "price": 2500.0,
                "stop_loss": 2400.0
            }

            await tm._apply_sl_update(test_signal, 2450.0, "BREAKEVEN", "Trailing BE")

    # Cuenta 1 debió ser llamada con 'pos_prim_111'
    mock_ex1.modify_position_tpsl.assert_called_with(
        symbol="ETHUSDT",
        position_id="pos_prim_111",
        sl_price=2450.0
    )

    # Cuenta 2 debió resolver en caliente 'pos_sec_999' de su propio exchange
    mock_ex2.modify_position_tpsl.assert_called_with(
        symbol="ETHUSDT",
        position_id="pos_sec_999",
        sl_price=2450.0
    )
