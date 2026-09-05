"""
engine/tests/test_multi_account_advanced_security_and_resilience.py
=============================================================================
SUITE AVANZADA DE SEGURIDAD, RESILIENCIA Y PARIDAD MULTI-CUENTA
=============================================================================
Valida:
  1. sync_live_bitunix_positions ejecuta Fast BE y trailing en cuentas secundarias.
  2. sync_live_bitunix_pending_orders purga órdenes huérfanas en múltiples cuentas.
  3. get_unprotected_risk_count aísla rigurosamente los slots de riesgo por cuenta.
  4. Cifrado y descifrado transparente AES-256 (Fernet) de credenciales en reposo.
  5. Resiliencia ante fallos: Un error 401/Timeout en una cuenta no tumba ni retrasa las demás.
  6. Kill-Switch institucional: Cierre de emergencia aislado por cuenta.
=============================================================================
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from engine.execution.account_manager import (
    AccountManager,
    BitunixAccountConfig,
    encrypt_credential,
    decrypt_credential
)
from engine.workers.trade_manager import TradeManager
from engine.execution.nexus import NexusNode


@pytest.mark.asyncio
class TestMultiAccountAdvancedSecurityAndResilience:

    def test_credential_encryption_and_decryption_at_rest(self):
        """Verifica que las credenciales se cifren con prefijo enc:v1: y se descifren íntegras."""
        secret = "secret_key_12345_institutional_quant"
        encrypted = encrypt_credential(secret)
        
        assert encrypted != secret
        assert encrypted.startswith("enc:v1:")
        
        # Idempotencia: no volver a cifrar si ya tiene el prefijo
        re_encrypted = encrypt_credential(encrypted)
        assert re_encrypted == encrypted
        
        decrypted = decrypt_credential(encrypted)
        assert decrypted == secret

    async def test_sync_live_bitunix_positions_across_all_accounts(self):
        """Verifica que TradeManager inspeccione y aplique BE en cuentas secundarias."""
        tm = TradeManager()
        
        mock_ex_primary = MagicMock()
        mock_ex_primary.account_label = "Primary"
        mock_ex_primary.get_pending_positions = AsyncMock(return_value=[])
        
        mock_ex_sec = MagicMock()
        mock_ex_sec.account_label = "Cliente 2"
        mock_ex_sec.get_pending_positions = AsyncMock(return_value=[
            {
                "symbol": "SOLUSDT",
                "side": "BUY",
                "avgOpenPrice": 150.0,
                "lastPrice": 154.0,  # +4.0 USDT (+1.33R con SL a 147)
                "slPrice": 147.0,
                "positionId": "pos_sec_999"
            }
        ])
        mock_ex_sec._request = AsyncMock(return_value={"code": 0, "data": []})
        mock_ex_sec.get_ticker_price = AsyncMock(return_value=154.0)
        mock_ex_sec.modify_position_tpsl = AsyncMock(return_value=True)

        with patch("engine.execution.account_manager.AccountManager.get_all_executors", return_value={
            "primary": mock_ex_primary,
            "cliente_2": mock_ex_sec
        }):
            results = await tm.sync_live_bitunix_positions()
            
            # Debe haber procesado la posición de cliente_2
            assert len(results) == 1
            res = results[0]
            assert res["account_id"] == "cliente_2"
            assert res["symbol"] == "SOLUSDT"
            assert "SL_ACTUALIZADO" in res["action"]
            mock_ex_sec.modify_position_tpsl.assert_awaited_once()

    async def test_sentinel_cancels_stale_limits_on_all_accounts(self):
        """Verifica que el Limit Sentinel cancele órdenes límite huérfanas en cuentas secundarias."""
        tm = TradeManager()
        
        mock_ex_sec = MagicMock()
        mock_ex_sec.account_label = "Cliente Secundario"
        mock_ex_sec.get_pending_orders = AsyncMock(return_value=[
            {
                "symbol": "BTCUSDT",
                "orderId": "order_missed_1",
                "side": "BUY",
                "price": 60000.0,
                "slPrice": 59000.0,
                "tradeSide": "OPEN",
                "orderType": "LIMIT",
                "ctime": 1000000000000
            }
        ])
        mock_ex_sec.get_pending_positions = AsyncMock(return_value=[])
        mock_ex_sec.purge_orphaned_close_orders = AsyncMock(return_value=0)
        mock_ex_sec.get_ticker_price = AsyncMock(return_value=63000.0)
        mock_ex_sec.cancel_limit_order = AsyncMock(return_value=True)

        with patch("engine.execution.account_manager.AccountManager.get_all_executors", return_value={"client_x": mock_ex_sec}):
            cancelled = await tm.sync_live_bitunix_pending_orders()
            assert len(cancelled) == 1
            assert cancelled[0]["account_id"] == "client_x"
            assert cancelled[0]["order_id"] == "order_missed_1"
            mock_ex_sec.cancel_limit_order.assert_awaited_once_with("BTCUSDT", "order_missed_1")

    def test_unprotected_risk_count_isolation_per_account(self):
        """Verifica que el conteo de posiciones con riesgo esté estrictamente aislado por cuenta."""
        nexus = NexusNode(dry_run=True)
        
        # Simular 4 posiciones con riesgo en la cuenta primaria
        nexus._active_positions = {
            "primary_BTCUSDT": {"account_id": "primary", "signal": {"asset": "BTCUSDT", "price": 60000, "stop_loss": 58000, "type": "LONG"}},
            "primary_ETHUSDT": {"account_id": "primary", "signal": {"asset": "ETHUSDT", "price": 3000, "stop_loss": 2900, "type": "LONG"}},
            "primary_SOLUSDT": {"account_id": "primary", "signal": {"asset": "SOLUSDT", "price": 150, "stop_loss": 140, "type": "LONG"}},
            "primary_AVAXUSDT": {"account_id": "primary", "signal": {"asset": "AVAXUSDT", "price": 30, "stop_loss": 28, "type": "LONG"}},
            # Cuenta secundaria solo tiene 1 posición
            "cliente_2_XRPUSDT": {"account_id": "cliente_2", "signal": {"asset": "XRPUSDT", "price": 1.35, "stop_loss": 1.30, "type": "LONG"}},
        }

        # La cuenta primaria debe tener 4 en riesgo (saturada)
        primary_risk = nexus.get_unprotected_risk_count(account_id="primary")
        assert primary_risk == 4

        # La cuenta secundaria SOLO debe tener 1 en riesgo (margen y cupo disponible)
        sec_risk = nexus.get_unprotected_risk_count(account_id="cliente_2")
        assert sec_risk == 1

    async def test_multi_account_resilience_on_single_account_failure(self):
        """Verifica que si una cuenta arroja un error 401 o excepción de red, las demás cuentas se ejecuten exitosamente."""
        nexus = NexusNode(dry_run=True)
        
        acc1 = BitunixAccountConfig(account_id="primary", label="Cuenta Primaria", api_key="k1", secret_key="s1", is_primary=True)
        acc2 = BitunixAccountConfig(account_id="faulty_user", label="Cuenta Con Error", api_key="k2", secret_key="s2")
        acc3 = BitunixAccountConfig(account_id="healthy_user", label="Cuenta Sana", api_key="k3", secret_key="s3")

        mock_ex1 = MagicMock()
        mock_ex1.dry_run = True
        mock_ex1.get_available_margin_usdt = AsyncMock(return_value=100.0)
        mock_ex1.get_symbol_precision = AsyncMock(return_value=(2, 4))
        mock_ex1.execute_signal = AsyncMock(return_value={"status": "success", "main_order_id": "ord_1"})

        mock_ex2 = MagicMock()
        mock_ex2.dry_run = False
        mock_ex2.get_available_margin_usdt = AsyncMock(side_effect=Exception("401 Unauthorized: Invalid API Key"))

        mock_ex3 = MagicMock()
        mock_ex3.dry_run = True
        mock_ex3.get_available_margin_usdt = AsyncMock(return_value=250.0)
        mock_ex3.get_symbol_precision = AsyncMock(return_value=(2, 4))
        mock_ex3.execute_signal = AsyncMock(return_value={"status": "success", "main_order_id": "ord_3"})

        with patch.object(nexus.account_manager, "get_all_accounts", return_value=[acc1, acc2, acc3]), \
             patch.object(nexus.account_manager, "get_executor", side_effect=lambda aid: {"primary": mock_ex1, "faulty_user": mock_ex2, "healthy_user": mock_ex3}.get(aid)):

            signal = {
                "asset": "LINKUSDT",
                "type": "LONG",
                "price": 15.0,
                "stop_loss": 14.5,
                "tp1": 16.0,
                "tp2": 17.0,
                "tp3": 18.0,
                "confluence_score": 85
            }

            await nexus.process_signal(signal)

            # Las cuentas 1 y 3 deben haberse ejecutado con éxito a pesar del fallo en la 2
            mock_ex1.execute_signal.assert_awaited_once()
            mock_ex3.execute_signal.assert_awaited_once()

    async def test_emergency_kill_switch_per_account(self):
        """Verifica que emergency_close_account cancele órdenes, liquide posiciones y pause la cuenta indicada."""
        mgr = AccountManager()
        
        test_acc = BitunixAccountConfig(
            account_id="client_kill_test",
            label="Cuenta Prueba KillSwitch",
            api_key="key_kill",
            secret_key="sec_kill",
            enabled=True
        )
        
        mock_ex = MagicMock()
        mock_ex.cancel_all_pending_orders = AsyncMock(return_value=True)
        mock_ex.get_pending_positions = AsyncMock(return_value=[
            {"symbol": "XRPUSDT", "qty": 100.0, "side": "BUY", "positionId": "pos_kill_1"}
        ])
        mock_ex.close_market_position = AsyncMock(return_value={"code": 0, "msg": "Closed"})

        mgr._accounts["client_kill_test"] = test_acc
        mgr._executors["client_kill_test"] = mock_ex

        res = await mgr.emergency_close_account("client_kill_test")

        assert res["status"] == "success"
        assert res["account_enabled"] is False
        assert test_acc.enabled is False
        mock_ex.cancel_all_pending_orders.assert_awaited_once()
        mock_ex.close_market_position.assert_awaited_once_with(symbol="XRPUSDT", side="SELL", qty=100.0, position_id="pos_kill_1")

        # Limpiar
        mgr.remove_account("client_kill_test")
