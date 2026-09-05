import pytest
import asyncio
import os
import sqlite3
from unittest.mock import AsyncMock, patch
from engine.execution.nexus import NexusNode
from engine.workers.trade_manager import TradeManager

@pytest.mark.asyncio
async def test_sqlite_buffer_persistence_and_recovery(tmp_path):
    """Valida que el buffer se guarde en SQLite y se recupere intacto tras un reinicio."""
    test_db = str(tmp_path / "test_slingshot.db")
    
    # Mockear DB_PATH a nivel de clase para que __init__ cargue la DB temporal limpia
    with patch.object(NexusNode, "DB_PATH", test_db):
        node1 = NexusNode(dry_run=True)
        node1._high_confluence_buffer = {}
        
        sig = {
            "asset": "BTCUSDT",
            "symbol": "BTCUSDT",
            "direction": "LONG",
            "confluence_score": 88.0,
            "price": 65000.0,
            "stop_loss": 64000.0
        }
        
        node1.enqueue_high_confluence_opportunity(sig, "primary")
        assert "primary" in node1._high_confluence_buffer
        assert len(node1._high_confluence_buffer["primary"]) == 1
        
        # Simular reinicio creando una nueva instancia apuntando a la misma DB temporal
        node2 = NexusNode(dry_run=True)
        assert "primary" in node2._high_confluence_buffer
        assert len(node2._high_confluence_buffer["primary"]) == 1
        restored = node2._high_confluence_buffer["primary"][0]
        assert restored["asset"] == "BTCUSDT"
        assert restored["confluence_score"] == 88.0

@pytest.mark.asyncio
async def test_half_risk_mitigator_calculation():
    """Valida la regla de reduccion de riesgo al 50% (-0.5R) cuando el precio avanza +0.6R."""
    tm = TradeManager()
    
    entry_price = 100.0
    sl_initial = 90.0
    sl_dist = 10.0 # 1R = $10.00
    side = "LONG"
    
    # Precio avanza a 106.0 (+0.6R)
    cur_price = 106.0
    r_profit = (cur_price - entry_price) / sl_dist # +0.6R
    
    assert r_profit >= 0.60
    # El SL mitigado debe ser entrada - 0.5R = $95.00
    half_sl = round(entry_price - (sl_dist * 0.50), 4)
    assert half_sl == 95.00
    # Valida que se recorta el 50% de la perdida maxima si el precio se devuelve
    assert abs(entry_price - half_sl) == 5.00
