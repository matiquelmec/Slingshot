"""
test_turso_sync.py — Unit Tests para Sincronización Dual-Engine Python ↔ Turso Cloud
"""

import pytest
from unittest.mock import patch, MagicMock
from engine.execution.turso_sync import TursoSyncManager

@pytest.fixture
def mock_turso_manager():
    manager = TursoSyncManager()
    manager.raw_url = "libsql://test-apex.turso.io"
    manager.token = "mock-jwt-token"
    manager._configure_endpoints()
    return manager

def test_turso_endpoint_configuration(mock_turso_manager):
    assert mock_turso_manager.is_enabled is True
    assert mock_turso_manager._http_url == "https://test-apex.turso.io/v2/pipeline"

def test_turso_disabled_graceful_handling():
    manager = TursoSyncManager()
    manager.raw_url = ""
    manager.token = ""
    manager._http_url = None
    manager._is_enabled = False

    assert manager.is_enabled is False
    res = manager.record_trade({"symbol": "BTCUSDT", "side": "BUY", "entry_price": 50000})
    assert res is None

    sig_res = manager.record_signal({"asset": "ETHUSDT", "direction": "LONG", "entry_price": 3000})
    assert sig_res is None

def test_record_signal_payload_structure(mock_turso_manager):
    with patch.object(mock_turso_manager, "execute_sql") as mock_exec:
        mock_exec.return_value = {"success": True}
        mock_turso_manager._initialized = True

        sig_id = mock_turso_manager.record_signal({
            "asset": "BTCUSDT",
            "direction": "LONG",
            "timeframe": "15m",
            "entry_price": 64500.0,
            "stop_loss": 63800.0,
            "take_profit_1": 65500.0,
            "confluence_score": 85.0,
            "ker_value": 0.65,
            "status": "PENDING"
        })

        assert sig_id is not None
        mock_exec.assert_called_once()
        sql_call = mock_exec.call_args[0][0]
        params = mock_exec.call_args[0][1]

        assert "INSERT INTO signals" in sql_call
        assert params[3] == "BTCUSDT"
        assert params[4] == "LONG"
        assert params[6] == 64500.0

def test_record_trade_payload_structure(mock_turso_manager):
    with patch.object(mock_turso_manager, "execute_sql") as mock_exec:
        mock_exec.return_value = {"success": True}
        mock_turso_manager._initialized = True

        trade_id = mock_turso_manager.record_trade({
            "symbol": "SOLUSDT",
            "side": "BUY",
            "entry_price": 142.50,
            "quantity": 10.0,
            "pnl": 15.2,
            "status": "OPEN"
        })

        assert trade_id is not None
        mock_exec.assert_called_once()
        sql_call = mock_exec.call_args[0][0]
        params = mock_exec.call_args[0][1]

        assert "INSERT OR REPLACE INTO trades" in sql_call
        assert params[3] == "SOLUSDT"
        assert params[4] == "BUY"
        assert params[5] == 142.50

def test_close_trade_execution(mock_turso_manager):
    with patch.object(mock_turso_manager, "execute_sql") as mock_exec:
        mock_exec.return_value = {"success": True}

        success = mock_turso_manager.close_trade(
            trade_id="trade-1234",
            exit_price=150.0,
            pnl=75.0,
            pnl_percent=5.26
        )

        assert success is True
        mock_exec.assert_called_once()
        sql_call = mock_exec.call_args[0][0]
        assert "UPDATE trades SET exit_price =" in sql_call
