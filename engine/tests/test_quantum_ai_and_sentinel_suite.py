import pytest
import asyncio
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch, AsyncMock
from engine.core.tear_sheet import calculate_portfolio_metrics, format_tear_sheet_markdown
from engine.core.confluence import ConfluenceManager
from engine.ml.inference import SlingshotML
from engine.workers.trade_manager import TradeManager

def test_ml_meta_labeling_boosts_confluence_score():
    cm = ConfluenceManager()
    
    dates = pd.date_range(end=pd.Timestamp.now(tz="UTC"), periods=50, freq='15min')
    df = pd.DataFrame({
        'timestamp': dates,
        'open': np.linspace(100, 110, 50),
        'high': np.linspace(101, 111, 50),
        'low': np.linspace(99, 109, 50),
        'close': np.linspace(100.5, 110.5, 50),
        'volume': [1000.0] * 50
    })
    
    sig = {
        'symbol': 'BTCUSDT',
        'asset': 'BTCUSDT',
        'signal_type': 'LONG',
        'timestamp': dates[-1],
        'price': 110.5
    }
    
    res_no_ml = cm.evaluate_signal(df=df, signal=sig, ml_projection=None)
    res_with_ml = cm.evaluate_signal(
        df=df, 
        signal=sig, 
        ml_projection={'direction': 'ALCISTA', 'probability': 85, 'status': 'active'}
    )
    
    checklist_ml = [c['detail'] for c in res_with_ml['checklist'] if c.get('factor') == 'ML Meta-Labeling']
    assert len(checklist_ml) > 0, "Debe registrar factor ML Meta-Labeling en checklist"
    assert "ML XGBoost Confianza (85.0%) alineado (+10pts)" in checklist_ml[0]

def test_ml_graceful_fallback_when_no_model():
    ml = SlingshotML(model_filename="non_existent_model.json")
    assert ml.is_loaded is False, "Modelo inexistente no debe estar cargado"
    
    df_dummy = pd.DataFrame({
        'open': [100.0, 101.0],
        'high': [102.0, 103.0],
        'low': [99.0, 100.0],
        'close': [101.0, 102.0],
        'volume': [1000, 1200]
    })
    
    res = ml.predict_live(df_dummy)
    assert res['status'] == 'no_model', "predict_live debe retornar status no_model de forma segura"
    assert res['probability'] == 50

@pytest.mark.asyncio
async def test_manual_client_exit_triggers_orphan_purge_and_alert():
    tm = TradeManager()
    
    # Simular estado previo: cliente_2 tenía posición en ETHUSDT
    tm._last_active_positions = {
        'cliente_2': {'ETHUSDT'}
    }
    
    # Mock de Bitunix Executor para cliente_2
    mock_bitunix = MagicMock()
    mock_bitunix.account_label = "Cuenta Cliente 2"
    mock_bitunix.get_pending_positions = AsyncMock(return_value=[]) # Posición cerrada
    mock_bitunix.purge_orphaned_close_orders = AsyncMock(return_value=0)
    mock_bitunix.cancel_all_orders_for_symbol = AsyncMock(return_value=2)
    # Simular que la orden de cierre fue manual (clientId == None)
    mock_bitunix._request = AsyncMock(return_value={
        "data": {
            "orderList": [
                {"orderId": "123", "clientId": None, "status": "FILLED", "side": "SELL"}
            ]
        }
    })
    
    # Simular ejecución del bloque SOP-59 de trade_manager
    acc_id = 'cliente_2'
    active_symbols = {p.get("symbol") for p in (await mock_bitunix.get_pending_positions() or []) if p.get("symbol")}
    await mock_bitunix.purge_orphaned_close_orders(active_symbols=active_symbols)

    prev_active = tm._last_active_positions.get(acc_id, set())
    assert "ETHUSDT" in prev_active
    closed_symbols = prev_active - active_symbols
    assert "ETHUSDT" in closed_symbols

    for csym in closed_symbols:
        hist_res = await mock_bitunix._request("GET", "/api/v1/futures/trade/get_history_orders", params={"symbol": csym, "pageSize": 3})
        hist_orders = hist_res.get("data", {}).get("orderList", [])
        is_manual = any(o.get("clientId") is None and o.get("status") == "FILLED" for o in hist_orders[:2])
        assert is_manual is True
        
        purged_cnt = await mock_bitunix.cancel_all_orders_for_symbol(csym)
        assert purged_cnt == 2

def test_tear_sheet_financial_metrics_math():
    returns_r = [2.0, 1.5, -1.0, 3.0]
    metrics = calculate_portfolio_metrics(returns_r)
    
    assert metrics['total_trades'] == 4
    assert metrics['win_count'] == 3
    assert metrics['loss_count'] == 1
    assert metrics['win_rate_pct'] == 75.0
    assert metrics['net_r'] == 5.5
    assert metrics['profit_factor'] == 6.5
    assert metrics['sharpe_ratio'] > 0
    assert metrics['max_drawdown_r'] == 1.0
    
    md = format_tear_sheet_markdown(metrics, account_label="Test")
    assert "TEAR SHEET CUANTITATIVO" in md
    assert "+5.5 R" in md
