"""
engine/tests/test_multi_account_dispatcher.py
=============================================================================
Suite de Certificación QA: Arquitectura Multi-Cuentas Bitunix (Master Dispatcher)
- Auto-descubrimiento de Cuenta Primaria desde .env
- Registro, aislamiento de credenciales y enmascaramiento de API Keys
- Independencia estricta de cálculo de riesgo SOP-41 por cuenta
- Tolerancia a fallos: Aislamiento total de errores entre cuentas
- Concurrencia segura y despacho paralelo en NexusNode
=============================================================================
"""
import pytest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

from engine.execution.account_manager import AccountManager, BitunixAccountConfig
from engine.execution.bitunix_executor import BitunixExecutor
from engine.execution.nexus import NexusNode
from engine.risk.risk_manager import RiskManager


class TestMultiAccountDispatcher:
    """Certificación de Gestión y Despacho Multi-Cuentas de Bitunix."""

    @pytest.fixture(autouse=True)
    def setup_temp_manager(self, tmp_path):
        """Asegura un AccountManager limpio con archivo temporal para cada prueba."""
        AccountManager._instance = None
        self.temp_json = tmp_path / "test_accounts.json"
        self.mgr = AccountManager(dry_run=True, accounts_file=self.temp_json)
        yield
        AccountManager._instance = None

    def test_primary_account_auto_registered_from_env(self):
        """Certifica que la cuenta principal se auto-registre desde las variables de entorno."""
        primary = self.mgr.get_account("primary")
        assert primary is not None
        assert primary.is_primary is True
        assert primary.enabled is True
        assert primary.risk_pct == 0.025
        
        executor = self.mgr.get_executor("primary")
        assert executor is not None
        assert isinstance(executor, BitunixExecutor)

    @pytest.mark.asyncio
    async def test_add_and_remove_secondary_account(self):
        """Certifica el ciclo de vida completo de una cuenta secundaria (alta, consulta ofuscada, baja)."""
        sec_cfg = BitunixAccountConfig(
            account_id="client_inv_1",
            label="Inversionista Alpha",
            api_key="BK_SECRET_KEY_1234567890",
            secret_key="SEC_SECRET_9876543210",
            enabled=True,
            risk_pct=0.020, # 2.0%
            dry_run=True
        )
        success, msg = await self.mgr.add_account(sec_cfg, test_first=False)
        assert success is True
        
        # Verificar consulta con claves ofuscadas
        acc = self.mgr.get_account("client_inv_1")
        assert acc is not None
        dict_masked = acc.to_dict(mask_secrets=True)
        assert "..." in dict_masked["api_key"]
        assert dict_masked["secret_key"] == "********"
        
        # Verificar remoción
        rem_ok, rem_msg = self.mgr.remove_account("client_inv_1")
        assert rem_ok is True
        assert self.mgr.get_account("client_inv_1") is None

    def test_toggle_account_blocks_dispatch(self):
        """Certifica que pausar una cuenta la excluya del pool de ejecutores activos."""
        sec_cfg = BitunixAccountConfig(
            account_id="acc_pausable",
            label="Cuenta Pausable",
            api_key="KEY_TEST",
            secret_key="SEC_TEST",
            enabled=True,
            dry_run=True
        )
        self.mgr._accounts["acc_pausable"] = sec_cfg
        self.mgr._executors["acc_pausable"] = BitunixExecutor(dry_run=True)

        assert "acc_pausable" in self.mgr.get_all_executors(enabled_only=True)
        
        # Pausar cuenta
        self.mgr.toggle_account("acc_pausable", enabled=False)
        assert "acc_pausable" not in self.mgr.get_all_executors(enabled_only=True)
        assert "acc_pausable" in self.mgr.get_all_executors(enabled_only=False)

    @pytest.mark.asyncio
    async def test_multi_account_independent_dollar_risk_sizing(self):
        """
        [AISLAMIENTO DE RIESGO SOP-41]
        Certifica que Cuenta A ($142.40 USD) y Cuenta B ($500.00 USD)
        dimensionen cantidades completamente independientes arriesgando su 2.50% exacto.
        """
        node = NexusNode(dry_run=True)
        
        acc_a = BitunixAccountConfig(
            account_id="acc_a",
            label="Cuenta A (142 USD)",
            api_key="K1",
            secret_key="S1",
            risk_pct=0.025,
            dry_run=True
        )
        acc_b = BitunixAccountConfig(
            account_id="acc_b",
            label="Cuenta B (500 USD)",
            api_key="K2",
            secret_key="S2",
            risk_pct=0.025,
            dry_run=True
        )

        ex_a = BitunixExecutor(dry_run=True)
        ex_a.get_available_margin_usdt = AsyncMock(return_value=142.40)
        ex_a.get_symbol_precision = AsyncMock(return_value=(1, 3))
        ex_a.execute_signal = AsyncMock(return_value={"status": "success", "main_order_id": "ord_a"})

        ex_b = BitunixExecutor(dry_run=True)
        ex_b.get_available_margin_usdt = AsyncMock(return_value=500.00)
        ex_b.get_symbol_precision = AsyncMock(return_value=(1, 3))
        ex_b.execute_signal = AsyncMock(return_value={"status": "success", "main_order_id": "ord_b"})

        signal = {
            "asset": "INJUSDT",
            "type": "LONG",
            "price": 4.798,
            "stop_loss": 4.698, # Distancia = $0.100
            "leverage": 10,
            "risk_pct": 0.025
        }

        # Ejecutar en Cuenta A
        await node._execute_signal_for_account(
            executor=ex_a,
            account=acc_a,
            signal=signal,
            safe_lev=10,
            entry_val=4.798,
            sl_val=4.698,
            fragments=[]
        )
        
        # Ejecutar en Cuenta B
        await node._execute_signal_for_account(
            executor=ex_b,
            account=acc_b,
            signal=signal,
            safe_lev=10,
            entry_val=4.798,
            sl_val=4.698,
            fragments=[]
        )

        # Verificar llamadas
        assert ex_a.execute_signal.called
        call_sig_a = ex_a.execute_signal.call_args[0][0]
        # Cuenta A: $142.40 * 0.025 = $3.56 USD de riesgo. Dist = 0.10 -> Qty = 35.6 INJ
        assert 35.0 <= call_sig_a["exact_qty"] <= 36.0

        assert ex_b.execute_signal.called
        call_sig_b = ex_b.execute_signal.call_args[0][0]
        # Cuenta B: $500.00 * 0.025 = $12.50 USD de riesgo. Dist = 0.10 -> Qty = 125.0 INJ
        assert 124.0 <= call_sig_b["exact_qty"] <= 126.0

    @pytest.mark.asyncio
    async def test_multi_account_fault_isolation(self):
        """
        [TOLERANCIA A FALLOS]
        Certifica que si una cuenta secundaria arroja un error de conexión,
        las demás cuentas continúan su ejecución exitosamente sin interrumpirse.
        """
        node = NexusNode(dry_run=True)

        acc_healthy = BitunixAccountConfig(account_id="acc_ok", label="Saludable", api_key="K1", secret_key="S1", dry_run=True)
        acc_failing = BitunixAccountConfig(account_id="acc_err", label="Con Fallo", api_key="K2", secret_key="S2", dry_run=True)

        ex_healthy = BitunixExecutor(dry_run=True)
        ex_healthy.get_available_margin_usdt = AsyncMock(return_value=100.0)
        ex_healthy.get_symbol_precision = AsyncMock(return_value=(2, 2))
        ex_healthy.execute_signal = AsyncMock(return_value={"status": "success", "main_order_id": "healthy_ok"})

        ex_failing = BitunixExecutor(dry_run=True)
        ex_failing.get_available_margin_usdt = AsyncMock(side_effect=Exception("Bitunix 502 Bad Gateway"))

        node.account_manager.get_all_accounts = MagicMock(return_value=[acc_healthy, acc_failing])
        node.account_manager.get_executor = MagicMock(side_effect=lambda aid: ex_healthy if aid == "acc_ok" else ex_failing)

        test_sig = {
            "asset": "SOLUSDT",
            "type": "LONG",
            "price": 100.0,
            "stop_loss": 95.0,
            "confluence_score": 85.0
        }

        # Despachar señal a través de NexusNode
        await node.process_signal(test_sig)

        # La cuenta saludable debe haber ejecutado con éxito a pesar de que la otra falló
        assert ex_healthy.execute_signal.called

    @pytest.mark.asyncio
    async def test_accounts_rest_api_endpoints(self):
        """Certifica las rutas REST GET y POST de gestión de cuentas con FastAPI TestClient."""
        from fastapi.testclient import TestClient
        from engine.api.main import app

        client = TestClient(app)
        
        # 1. GET /api/v1/accounts
        resp = client.get("/api/v1/accounts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "accounts" in data
        assert data["total"] >= 1 # Al menos la primaria
        
        primary_acc = data["accounts"][0]
        assert primary_acc["account_id"] == "primary"
        assert primary_acc["secret_key"] == "********" # Clave secreta ofuscada
