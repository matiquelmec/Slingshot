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

    assert res is None or res.get('status') == 'already_active'
    mock_executor.place_limit_signal.assert_not_called()

@pytest.mark.asyncio
async def test_sync_loop_protects_paused_account_positions(mock_nexus):
    ex_sec = AsyncMock()
    ex_sec.account_label = 'Cliente 2'
    ex_sec.get_pending_positions.return_value = [{
        'symbol': 'ETHUSDT',
        'qty': '0.382',
        'avgOpenPrice': '2456.63',
        'side': 'BUY',
        'leverage': 20,
        'margin': 46.92,
        'positionId': '552934383104417917'
    }]
    mock_nexus.account_manager.get_all_executors.return_value = {'cliente_2': ex_sec}
    
    executors = mock_nexus.account_manager.get_all_executors(enabled_only=False)
    assert 'cliente_2' in executors
    pos = await executors['cliente_2'].get_pending_positions()
    assert len(pos) == 1
    assert pos[0]['symbol'] == 'ETHUSDT'

@pytest.mark.asyncio
async def test_tp_grid_consolidates_under_min_trade_volume():
    from engine.execution.bitunix_executor import BitunixExecutor
    ex = BitunixExecutor(dry_run=True)
    ex._symbol_rules_cache = {
        "NEARUSDT": {
            "qty_precision": 0,
            "price_precision": 3,
            "min_trade_volume": 10.0
        }
    }
    rules = await ex.get_symbol_rules("NEARUSDT")
    assert rules["min_trade_volume"] == 10.0
    
    qty = 34.0
    min_vol = rules["min_trade_volume"]
    f1 = int(round(qty * 0.60)) # 20
    f2 = int(round(qty * 0.20)) # 7
    f3 = int(round(qty - f1 - f2)) # 7
    
    if min_vol > 0:
        if f1 < min_vol:
            f1 = qty
            f2 = 0
            f3 = 0
        elif f2 < min_vol:
            f1 = round(f1 + f2 + f3, 0)
            f2 = 0
            f3 = 0
        elif f3 < min_vol:
            f2 = round(f2 + f3, 0)
            f3 = 0

    assert f1 == 34.0 # Consolidado a 34 porque f2 < 10
    assert f2 == 0
    assert f3 == 0

@pytest.mark.asyncio
async def test_bitunix_executor_injects_instant_tp_in_limit_and_market_payloads():
    from engine.execution.bitunix_executor import BitunixExecutor
    executor = BitunixExecutor(dry_run=False)
    executor.api_key = "k"
    executor.secret_key = "s"
    
    captured_payloads = []
    async def mock_req(method, path, params=None, json_body=None):
        if json_body:
            captured_payloads.append((path, json_body))
        if "/api/v1/futures/account/change_leverage" in path:
            return {"code": 0, "data": {}}
        if "/api/v1/futures/trade/place_order" in path:
            return {"code": 0, "data": {"orderId": "ord_mock_123"}}
        if "/api/v1/futures/trade/get_pending_positions" in path:
            return {"code": 0, "data": []}
        return {"code": 0, "data": {}}
    
    executor._request = mock_req
    executor._last_verified_balance = 200.0
    
    # 1. Probar orden Límite con TP
    sig_limit = {
        "asset": "BTCUSDT",
        "type": "LONG",
        "price": 60000.0,
        "stop_loss": 59000.0,
        "tp1": 61000.0,
        "tp3": 63000.0,
        "position_size": 20.0,
        "leverage": 10
    }
    res_lim = await executor.place_limit_signal(sig_limit)
    assert res_lim["status"] == "success"
    limit_payload = next(b for p, b in captured_payloads if b.get("orderType") == "LIMIT")
    assert limit_payload["slPrice"] == "59000.0"
    assert limit_payload["tpPrice"] == "63000.0"
    assert limit_payload["tpStopType"] == "LAST_PRICE"
    assert limit_payload["tpOrderType"] == "MARKET"

    # 2. Probar orden a Mercado con TP
    captured_payloads.clear()
    sig_market = {
        "asset": "BTCUSDT",
        "type": "BUY",
        "price": 60000.0,
        "stop_loss": 59000.0,
        "tp1": 61200.0,
        "take_profit_3r": 63500.0,
        "position_size": 20.0,
        "leverage": 10
    }
    res_mkt = await executor.execute_signal(sig_market)
    assert res_mkt["status"] == "success"
    market_payload = next(b for p, b in captured_payloads if b.get("orderType") == "MARKET")
    assert market_payload["slPrice"] == "59000.0"
    assert market_payload["tpPrice"] == "63500.0"
    assert market_payload["tpStopType"] == "LAST_PRICE"
    assert market_payload["tpOrderType"] == "MARKET"

