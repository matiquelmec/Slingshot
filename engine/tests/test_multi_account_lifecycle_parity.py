"""
engine/tests/test_multi_account_lifecycle_parity.py
=============================================================================
Suite de Certificación QA: Paridad Multi-Cuenta de Ciclo de Vida y Resiliencia
- Paridad de Trailing Stop y Fast Breakeven en múltiples cuentas
- Preflight Notional Clamp ($5.00 USDT min Bitunix)
- Aislamiento estricto de Portfolio Heat por cuenta (SOP-44)
- Purga atómica de límites en múltiples ejecutores (SOP-22 / SOP-45)
- Caché compartida de offset de reloj del servidor (SOP-11)
=============================================================================
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from engine.execution.account_manager import AccountManager, BitunixAccountConfig
from engine.execution.bitunix_executor import BitunixExecutor
from engine.execution.nexus import NexusNode
from engine.risk.risk_manager import RiskManager
from engine.workers.trade_manager import TradeManager


class TestMultiAccountLifecycleParity:
    """Certifica la simetría y robustez del ciclo de vida multi-cuenta."""

    @pytest.mark.asyncio
    async def test_trailing_sl_updates_across_all_enabled_accounts(self):
        tm = TradeManager()

        acc1 = BitunixAccountConfig(account_id="primary", label="Primaria", api_key="K1", secret_key="S1", dry_run=False)
        acc2 = BitunixAccountConfig(account_id="client_2", label="Secundaria", api_key="K2", secret_key="S2", dry_run=False)

        ex1 = BitunixExecutor(dry_run=False)
        ex1.account_label = "Primaria"
        ex1.modify_position_tpsl = AsyncMock(return_value=True)

        ex2 = BitunixExecutor(dry_run=False)
        ex2.account_label = "Secundaria"
        ex2.modify_position_tpsl = AsyncMock(return_value=True)

        mock_executors = {"primary": ex1, "client_2": ex2}

        sig = {
            "asset": "XRPUSDT",
            "position_id": "pos_123",
            "status": "ACTIVE",
            "trailing_history": []
        }

        with patch("engine.execution.account_manager.AccountManager.get_all_executors", return_value=mock_executors),              patch("engine.core.store.store.save_signal", new_callable=AsyncMock):

            await tm._apply_sl_update(sig, new_sl=1.3550, new_phase="BREAKEVEN", reason="Fast BE hit")

            ex1.modify_position_tpsl.assert_called_once_with(symbol="XRPUSDT", position_id="pos_123", sl_price=1.3550)
            ex2.modify_position_tpsl.assert_called_once_with(symbol="XRPUSDT", position_id="pos_123", sl_price=1.3550)
            assert sig["stop_loss"] == 1.3550
            assert sig["trailing_phase"] == "BREAKEVEN"

    def test_preflight_notional_clamp_rejects_under_5_usdt(self):
        res = RiskManager.calculate_dollar_risk_position(
            account_balance=10.0,
            risk_pct=0.025,
            entry_price=100.0,
            sl_price=90.0,
            leverage=10,
            qty_decimals=3,
            min_notional_usdt=5.0
        )
        assert res["approved"] is False
        assert "inferior al mínimo de Bitunix" in res["reason"]

    def test_preflight_notional_clamp_approves_valid_sizes(self):
        res = RiskManager.calculate_dollar_risk_position(
            account_balance=300.0,
            risk_pct=0.025,
            entry_price=1.3543,
            sl_price=1.3299,
            leverage=20,
            qty_decimals=1,
            min_notional_usdt=5.0
        )
        assert res["approved"] is True
        assert res["notional_value"] >= 5.0
        assert res["qty"] > 0

    def test_portfolio_heat_isolation_by_account_id(self):
        active_positions = {
            "primary_BTCUSDT": {
                "account_id": "primary",
                "risk_usd": 6.0,
                "signal": {"type": "LONG", "price": 90000.0, "stop_loss": 89000.0}
            },
            "primary_ETHUSDT": {
                "account_id": "primary",
                "risk_usd": 4.0,
                "signal": {"type": "LONG", "price": 2500.0, "stop_loss": 2450.0}
            }
        }

        ok_client2, msg_client2, heat_client2 = RiskManager.check_portfolio_heat(
            active_positions=active_positions,
            new_direction="LONG",
            new_trade_risk_usd=7.50,
            account_balance=300.0,
            max_heat_pct=0.075,
            account_id="client_2"
        )
        assert ok_client2 is True
        assert heat_client2 == 0.0

        ok_primary, msg_primary, heat_primary = RiskManager.check_portfolio_heat(
            active_positions=active_positions,
            new_direction="LONG",
            new_trade_risk_usd=2.50,
            account_balance=100.0,
            max_heat_pct=0.075,
            account_id="primary"
        )
        assert ok_primary is False
        assert "SOP-44 HEAT VETO" in msg_primary
        assert heat_primary == 10.0

    @pytest.mark.asyncio
    async def test_purge_all_pending_limit_orders_multi_account(self):
        node = NexusNode(dry_run=True)

        ex1 = BitunixExecutor(dry_run=True)
        ex1.get_pending_orders = AsyncMock(return_value=[{"symbol": "XRPUSDT", "orderId": "111", "orderType": "LIMIT", "tradeSide": "OPEN"}])
        ex1.cancel_limit_order = AsyncMock(return_value=True)

        ex2 = BitunixExecutor(dry_run=True)
        ex2.get_pending_orders = AsyncMock(return_value=[{"symbol": "XRPUSDT", "orderId": "222", "orderType": "LIMIT", "tradeSide": "OPEN"}])
        ex2.cancel_limit_order = AsyncMock(return_value=True)

        with patch.object(node.account_manager, "get_all_executors", return_value={"primary": ex1, "client_2": ex2}):
            await node.purge_all_pending_limit_orders(reason="TEST_PURGE")

        ex1.cancel_limit_order.assert_called_once_with("XRPUSDT", "111")
        ex2.cancel_limit_order.assert_called_once_with("XRPUSDT", "222")

    def test_shared_time_offset_cache_across_instances(self):
        BitunixExecutor._shared_server_time_offset_ms = 450
        BitunixExecutor._shared_last_time_sync = 1000000.0

        ex1 = BitunixExecutor(dry_run=True, account_id="acc1")
        ex2 = BitunixExecutor(dry_run=True, account_id="acc2")

        ts1 = ex1.get_calibrated_timestamp_ms()
        ts2 = ex2.get_calibrated_timestamp_ms()

        assert abs(ts1 - ts2) <= 10
