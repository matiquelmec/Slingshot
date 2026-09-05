import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from engine.execution.nexus import NexusNode
from engine.core.store import store

@pytest.fixture(autouse=True)
def clean_nexus_buffer():
    # Limpiar buffer para que los tests no lean datos residuales de sqlite
    pass

@pytest.mark.asyncio
async def test_slot_recycler_ignores_when_max_slots_reached():
    engine = NexusNode(dry_run=True)
    engine._high_confluence_buffer = {} # Aislar para este test
    engine.MAX_CONCURRENT_POSITIONS = 4
    with patch.object(engine, "get_unprotected_risk_count", return_value=4):
        with patch.object(engine, "process_limit_setup", new_callable=AsyncMock) as mock_limit:
            await engine.on_risk_released("primary", reason="TEST")
            mock_limit.assert_not_called()

@pytest.mark.asyncio
async def test_slot_recycler_triggers_best_opportunity_from_store():
    engine = NexusNode(dry_run=True)
    engine._high_confluence_buffer = {} # Aislar para que consulte store
    engine.MAX_CONCURRENT_POSITIONS = 4
    fake_opps = [
        {"asset": "PAXGUSDT", "confluence_score": 62, "direction": "LONG", "price": 4350.0, "stop_loss": 4300.0, "tp1": 4400.0, "tp2": 4450.0, "tp3": 4500.0},
        {"asset": "SOLUSDT", "confluence_score": 75, "direction": "LONG", "price": 105.0, "stop_loss": 102.0, "tp1": 108.0, "tp2": 110.0, "tp3": 115.0}
    ]
    await store.save_scanner_opportunities("swing", fake_opps)

    with patch.object(engine, "get_unprotected_risk_count", return_value=3):
        with patch.object(engine, "process_limit_setup", new_callable=AsyncMock) as mock_limit:
            await engine.on_risk_released("primary", reason="POSICION_CERRADA_MANUAL")
            await asyncio.sleep(0.05)
            assert mock_limit.call_count == 1
            call_sig = mock_limit.call_args[0][0]
            assert call_sig["asset"] == "SOLUSDT"
            assert call_sig["confluence_score"] == 75

@pytest.mark.asyncio
async def test_slot_recycler_deduplicates_existing_positions():
    engine = NexusNode(dry_run=True)
    engine._high_confluence_buffer = {} # Aislar para que consulte store
    engine.MAX_CONCURRENT_POSITIONS = 4
    engine._active_positions["primary_SOLUSDT"] = {"asset": "SOLUSDT"}
    fake_opps = [
        {"asset": "PAXGUSDT", "confluence_score": 62, "direction": "LONG", "price": 4350.0, "stop_loss": 4300.0, "tp1": 4400.0, "tp2": 4450.0, "tp3": 4500.0},
        {"asset": "SOLUSDT", "confluence_score": 75, "direction": "LONG", "price": 105.0, "stop_loss": 102.0, "tp1": 108.0, "tp2": 110.0, "tp3": 115.0}
    ]
    await store.save_scanner_opportunities("swing", fake_opps)

    with patch.object(engine, "get_unprotected_risk_count", return_value=3):
        with patch.object(engine, "process_limit_setup", new_callable=AsyncMock) as mock_limit:
            await engine.on_risk_released("primary", reason="FAST_BE_ACTIVADO")
            await asyncio.sleep(0.05)
            assert mock_limit.call_count == 1
            call_sig = mock_limit.call_args[0][0]
            assert call_sig["asset"] == "PAXGUSDT"
