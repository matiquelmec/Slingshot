import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from engine.execution.nexus import NexusNode
from engine.execution.account_manager import BitunixAccountConfig

@pytest.fixture
def mock_nexus():
    node = NexusNode(dry_run=False)
    node._active_positions = {}
    node._pending_limit_symbols = set()
    node.account_manager = MagicMock()
    return node

@pytest.mark.asyncio
async def test_execute_signal_dedup_guard_memory(mock_nexus):
    mock_nexus._active_positions['cliente_2_NEARUSDT'] = {
        'signal': {'asset': 'NEARUSDT'},
        'status': 'OPEN',
        'account_id': 'cliente_2'
    }

    mock_account = BitunixAccountConfig(
        account_id='cliente_2',
        label='Cliente 2',
        api_key='k2',
        secret_key='s2',
        dry_run=False
    )
    mock_executor = AsyncMock()
    mock_executor.dry_run = False

    sig = {
        'asset': 'NEARUSDT',
        'type': 'LONG',
        'price': 2.19,
        'stop_loss': 2.15
    }

    res = await mock_nexus._execute_signal_for_account(
        executor=mock_executor,
        account=mock_account,
        signal=sig,
        safe_lev=10,
        entry_val=2.19,
        sl_val=2.15,
        fragments=[]
    )

    assert res is None
    mock_executor.execute_signal.assert_not_called()

@pytest.mark.asyncio
async def test_execute_signal_dedup_guard_exchange_live(mock_nexus):
    mock_account = BitunixAccountConfig(
        account_id='primary',
        label='Primary',
        api_key='k1',
        secret_key='s1',
        dry_run=False,
        is_primary=True
    )
    mock_executor = AsyncMock()
    mock_executor.dry_run = False
    mock_executor.get_pending_positions.return_value = [{'symbol': 'NEARUSDT', 'qty': '34'}]

    sig = {
        'asset': 'NEARUSDT',
        'type': 'LONG',
        'price': 2.19,
        'stop_loss': 2.15
    }

    res = await mock_nexus._execute_signal_for_account(
        executor=mock_executor,
        account=mock_account,
        signal=sig,
        safe_lev=10,
        entry_val=2.19,
        sl_val=2.15,
        fragments=[]
    )

    assert res is None
    mock_executor.execute_signal.assert_not_called()

@pytest.mark.asyncio
async def test_place_limit_dedup_guard_exchange(mock_nexus):
    mock_account = BitunixAccountConfig(
        account_id='cliente_2',
        label='Cliente 2',
        api_key='k2',
        secret_key='s2',
        dry_run=False
    )
    mock_executor = AsyncMock()
    mock_executor.dry_run = False
    mock_executor.get_pending_positions.return_value = [{'symbol': 'NEARUSDT', 'qty': '81'}]

    sig = {
        'asset': 'NEARUSDT',
        'type': 'LONG',
        'price': 2.19,
        'stop_loss': 2.15
    }

    res = await mock_nexus._place_limit_for_account(
        executor=mock_executor,
        account=mock_account,
        signal=sig,
        safe_lev=10,
        entry_p=2.19,
        sl_p=2.15
    )

    assert res is None
    mock_executor.place_limit_signal.assert_not_called()
